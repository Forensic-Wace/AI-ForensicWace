"""Authentication: local users, argon2id passwords, JWT session cookie.

The session travels in an httpOnly SameSite=Strict cookie rather than an
Authorization header because the SPA relies on EventSource (SSE progress)
and plain ``<a>``/``<img>`` links for media and PDF exports — none of which
can attach headers. Deployment is same-origin (nginx and the vite dev server
both proxy ``/api``), so there is no CORS surface and SameSite covers CSRF.

Sessions are stateless JWTs, but every request re-reads the user row (PK
lookup): disabling an account or bumping ``token_version`` revokes all its
outstanding sessions instantly — worth far more than purity here.
"""

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import func

from forensicwace_core.config import get_settings
from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import AuditLog, User

logger = logging.getLogger(__name__)

COOKIE_NAME = "fw_session"
ALGORITHM = "HS256"

# login rate limit: max failures per username within the window
MAX_LOGIN_FAILURES = 5
FAILURE_WINDOW_SECONDS = 300

_hasher = PasswordHasher()  # argon2id with library defaults

_ephemeral_secret: str | None = None


@dataclass(frozen=True)
class AuthUser:
    id: int | None
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


def _secret() -> str:
    settings = get_settings()
    if settings.jwt_secret:
        return settings.jwt_secret
    global _ephemeral_secret
    if _ephemeral_secret is None:
        _ephemeral_secret = secrets.token_urlsafe(48)
        logger.warning(
            "FW_JWT_SECRET is not set — using an ephemeral secret: sessions will not "
            "survive an API restart and cannot span replicas"
        )
    return _ephemeral_secret


def issue_token(user: User) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role or "analyst",
        "tv": user.token_version or 0,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.session_hours),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def get_current_user(request: Request) -> AuthUser:
    """FastAPI dependency guarding every /api/v1 route (see main.create_app)."""
    if get_settings().auth_disabled:
        return AuthUser(id=None, username="auth-disabled", role="admin")

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    with session_scope() as session:
        user = session.get(User, int(payload["sub"]))
        if (
            user is None
            or not user.is_active
            or user.username != payload.get("username")
            or (user.token_version or 0) != payload.get("tv")
        ):
            raise HTTPException(status_code=401, detail="Session revoked")
        return AuthUser(id=user.id, username=user.username, role=user.role or "analyst")


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator role required")
    return user


# --- Login attempt throttling ---------------------------------------------------


def check_login_allowed(username: str) -> None:
    """Throttle by counting recent ``auth.login_failed`` audit entries.

    The audit trail is the shared store, so the limit holds across API
    replicas with no extra infrastructure. Failures older than the window —
    or older than the account's last successful login — don't count. If the
    audit table cannot be read the login proceeds: the credential check right
    after needs the same database anyway.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=FAILURE_WINDOW_SECONDS)
    try:
        with session_scope() as session:
            last_success = (
                session.query(func.max(AuditLog.at))
                .filter(AuditLog.action == "auth.login", AuditLog.username == username)
                .scalar()
            )
            if last_success is not None:
                if last_success.tzinfo is None:
                    last_success = last_success.replace(tzinfo=timezone.utc)
                cutoff = max(cutoff, last_success)
            failures = (
                session.query(func.count(AuditLog.id))
                .filter(
                    AuditLog.action == "auth.login_failed",
                    AuditLog.resource == username,
                    AuditLog.at > cutoff,
                )
                .scalar()
            )
    except Exception:
        logger.warning("Login throttle check skipped — audit trail unreadable", exc_info=True)
        return
    if (failures or 0) >= MAX_LOGIN_FAILURES:
        raise HTTPException(status_code=429, detail="Too many failed attempts — retry later")


# --- Bootstrap -------------------------------------------------------------------


def ensure_bootstrap_admin() -> None:
    """Idempotent first-run admin creation from FW_ADMIN_USERNAME/PASSWORD."""
    settings = get_settings()
    if settings.auth_disabled or not settings.database_url:
        return
    with session_scope() as session:
        has_accounts = session.query(User).filter(User.username.isnot(None)).first() is not None
        if settings.admin_username and settings.admin_password:
            existing = session.query(User).filter_by(username=settings.admin_username).first()
            if existing is None:
                session.add(
                    User(
                        name=settings.admin_username,
                        surname="",
                        username=settings.admin_username,
                        password_hash=hash_password(settings.admin_password),
                        role="admin",
                        is_active=True,
                        token_version=0,
                        created_at=datetime.now(timezone.utc),
                    )
                )
                logger.info("Bootstrap admin %r created", settings.admin_username)
        elif not has_accounts:
            logger.warning(
                "Authentication is enabled but no user accounts exist and no "
                "FW_ADMIN_USERNAME/FW_ADMIN_PASSWORD are set — nobody can log in"
            )
