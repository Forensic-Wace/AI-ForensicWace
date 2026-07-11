"""Login/logout/session endpoints. The ``/auth`` routes for logging in
(password and OIDC) are the only ones under ``/api/v1`` reachable without a
session."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from forensicwace_core.config import get_settings
from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import User

from .. import audit, auth, oidc
from ..schemas import LoginRequest, MeOut, ProvidersOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=MeOut)
def login(body: LoginRequest, response: Response):
    settings = get_settings()
    if settings.auth_disabled:
        return MeOut(id=None, username="auth-disabled", role="admin", auth_disabled=True)

    auth.check_login_allowed(body.username)
    with session_scope() as session:
        user = session.query(User).filter_by(username=body.username).first()
        if (
            user is None
            or not user.is_active
            or not user.password_hash
            or not auth.verify_password(user.password_hash, body.password)
        ):
            # the audit entry doubles as the rate-limit counter (check_login_allowed)
            audit.record(None, "auth.login_failed", resource=body.username)
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user.last_login = datetime.now(timezone.utc)
        token = auth.issue_token(user)
        out = MeOut(id=user.id, username=user.username, role=user.role or "analyst")

    auth.set_session_cookie(response, token)
    audit.record(auth.AuthUser(id=out.id, username=out.username, role=out.role), "auth.login")
    return out


@router.get("/providers", response_model=ProvidersOut)
def providers():
    """Login methods available to the SPA login page (public)."""
    settings = get_settings()
    return ProvidersOut(password=not settings.auth_disabled, oidc=settings.oidc_enabled)


@router.get("/oidc/login")
def oidc_login(request: Request):
    """Kick off the authorization-code flow: redirect the browser to the IdP."""
    settings = get_settings()
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="Single sign-on is not configured")
    url, state = oidc.authorization_url(request)
    response = RedirectResponse(url, status_code=307)
    # Lax, not Strict: the callback arrives as a top-level cross-site redirect
    response.set_cookie(
        oidc.STATE_COOKIE,
        state,
        max_age=oidc.STATE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/api/v1/auth/oidc",
    )
    return response


@router.get("/oidc/callback")
def oidc_callback(request: Request, code: str, state: str):
    settings = get_settings()
    if not settings.oidc_enabled:
        raise HTTPException(status_code=404, detail="Single sign-on is not configured")
    claims = oidc.exchange_code(request, code, state, request.cookies.get(oidc.STATE_COOKIE))
    username = claims.get(settings.oidc_username_claim) or claims.get("sub")
    if not username:
        raise HTTPException(status_code=502, detail="ID token carries no usable username claim")

    with session_scope() as session:
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            user = User(
                name=claims.get("name") or username,
                surname="",
                username=username,
                password_hash=None,  # SSO-only account: password login stays impossible
                role="analyst",
                is_active=True,
                token_version=0,
                created_at=datetime.now(timezone.utc),
            )
            session.add(user)
            session.flush()
            audit.record(None, "user.provisioned", resource=username, detail="oidc")
        if not user.is_active:
            audit.record(None, "auth.login_failed", resource=username, detail="oidc: account disabled")
            raise HTTPException(status_code=403, detail="Account disabled")
        user.last_login = datetime.now(timezone.utc)
        token = auth.issue_token(user)
        out = MeOut(id=user.id, username=user.username, role=user.role or "analyst")

    response = RedirectResponse("/", status_code=303)
    auth.set_session_cookie(response, token)
    response.delete_cookie(oidc.STATE_COOKIE, path="/api/v1/auth/oidc")
    audit.record(auth.AuthUser(id=out.id, username=out.username, role=out.role), "auth.login", detail="oidc")
    return response


@router.post("/logout", status_code=204)
def logout(response: Response, user: auth.AuthUser = Depends(auth.get_current_user)):
    auth.clear_session_cookie(response)
    audit.record(user, "auth.logout")


@router.get("/me", response_model=MeOut)
def me(user: auth.AuthUser = Depends(auth.get_current_user)):
    return MeOut(
        id=user.id,
        username=user.username,
        role=user.role,
        auth_disabled=get_settings().auth_disabled,
    )
