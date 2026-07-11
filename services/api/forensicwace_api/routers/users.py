"""Operator account management (admin only).

Accounts are disabled, never deleted: their id is referenced by findings and
work items (chain of custody). Disabling or resetting a password bumps
``token_version``, revoking every outstanding session of that user.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import User

from ..auth import AuthUser, hash_password, require_admin
from ..schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role or "analyst",
        is_active=bool(user.is_active),
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.get("", response_model=list[UserOut])
def list_users():
    with session_scope() as session:
        accounts = session.query(User).filter(User.username.isnot(None)).order_by(User.username).all()
        return [_to_out(u) for u in accounts]


@router.post("", response_model=UserOut, status_code=201)
def create_user(request: UserCreate):
    with session_scope() as session:
        if session.query(User).filter_by(username=request.username).first() is not None:
            raise HTTPException(status_code=409, detail=f"Username {request.username!r} already exists")
        user = User(
            name=request.username,
            surname="",
            username=request.username,
            password_hash=hash_password(request.password),
            role=request.role,
            is_active=True,
            token_version=0,
            created_at=datetime.now(timezone.utc),
        )
        session.add(user)
        session.flush()
        return _to_out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, request: UserUpdate, admin: AuthUser = Depends(require_admin)):
    with session_scope() as session:
        user = session.get(User, user_id)
        if user is None or not user.username:
            raise HTTPException(status_code=404, detail="User not found")

        if user.id == admin.id and (request.is_active is False or (request.role and request.role != "admin")):
            raise HTTPException(status_code=409, detail="You cannot disable or demote your own account")

        revoke_sessions = False
        if request.role is not None:
            user.role = request.role
        if request.is_active is not None:
            user.is_active = request.is_active
            revoke_sessions = revoke_sessions or not request.is_active
        if request.password is not None:
            user.password_hash = hash_password(request.password)
            revoke_sessions = True
        if revoke_sessions:
            user.token_version = (user.token_version or 0) + 1
        return _to_out(user)
