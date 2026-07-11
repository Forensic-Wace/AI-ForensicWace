"""Login/logout/session endpoints. ``/auth/login`` is the only route under
``/api/v1`` reachable without a session."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from forensicwace_core.config import get_settings
from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import User

from .. import audit, auth
from ..schemas import LoginRequest, MeOut

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
