"""Audit trail access (admin only)."""

from fastapi import APIRouter, Depends, Query

from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import AuditLog

from ..auth import require_admin
from ..schemas import AuditEntryOut

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[AuditEntryOut])
def list_audit(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, description="Filter by exact action, e.g. auth.login"),
):
    with session_scope() as session:
        query = session.query(AuditLog).order_by(AuditLog.at.desc(), AuditLog.id.desc())
        if action:
            query = query.filter(AuditLog.action == action)
        return [
            AuditEntryOut(
                id=entry.id,
                at=entry.at,
                user_id=entry.user_id,
                username=entry.username,
                action=entry.action,
                resource=entry.resource,
                detail=entry.detail,
            )
            for entry in query.offset(offset).limit(limit)
        ]
