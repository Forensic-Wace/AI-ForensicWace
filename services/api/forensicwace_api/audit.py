"""Append-only audit trail of operator actions (chain of custody).

``record`` must never break the operation it documents: failures are logged
and swallowed. Entries are written in their own short transaction so they
survive even when the surrounding request later fails.
"""

import logging
from datetime import datetime, timezone

from forensicwace_core.config import get_settings
from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import AuditLog

from .auth import AuthUser

logger = logging.getLogger(__name__)


def record(user: AuthUser | None, action: str, resource: str = "", detail: str = "") -> None:
    if not get_settings().database_url:
        return
    try:
        with session_scope() as session:
            session.add(
                AuditLog(
                    at=datetime.now(timezone.utc),
                    user_id=user.id if user else None,
                    username=user.username if user else None,
                    action=action,
                    resource=resource[:255],
                    detail=detail,
                )
            )
    except Exception:
        logger.warning("Audit write failed for action %s on %s", action, resource, exc_info=True)
