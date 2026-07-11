"""AI analysis job submission and results.

Phase 1 executes jobs in a daemon thread; the ``process_status`` table is the
source of truth for progress, so the API stays stateless and the executor can
move behind a message queue (Phase 3) without any API change.
"""

import json
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from forensicwace_core.backups.android import resolve_db_path
from forensicwace_core.backups.ios import chatstorage_path, resolve_backup_dir
from forensicwace_core.config import get_settings
from forensicwace_core.constants import Platform
from forensicwace_core.analysis import registry
from forensicwace_core.analysis.dispatch import dispatch_analysis
from forensicwace_core.resultsdb import repositories
from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import ProcessStatus

from ..auth import AuthUser, get_current_user
from ..schemas import AnalysisRequest, AnalysisSubmitted, FindingOut, ProcessOut, TextResultOut

router = APIRouter(prefix="/analyses", tags=["analysis"])

SSE_POLL_SECONDS = 2
SSE_MAX_SECONDS = 3600


def _to_process_out(process: ProcessStatus) -> ProcessOut:
    return ProcessOut(
        process_id=process.process_id,
        platform=process.OS,
        backup_id=process.extraction_name_udid,
        status=process.status,
        details=process.details,
        start_time=process.start_time,
        end_time=process.end_time,
        analyzers=[a for a in (process.analyzers or "").split(",") if a],
        total_messages=process.total_messages or 0,
        analyzed_messages=process.analyzed_messages or 0,
        failed_messages=process.failed_messages or 0,
    )


@router.post("", response_model=AnalysisSubmitted, status_code=202)
def submit_analysis(request: AnalysisRequest, user: AuthUser = Depends(get_current_user)):
    problems = registry.validate_requested(request.analyzers)
    if problems:
        raise HTTPException(status_code=422, detail="; ".join(problems))

    settings = get_settings()
    if request.platform == Platform.ANDROID:
        db_path = resolve_db_path(settings.android_dir, request.backup_id, request.db_file)
    else:
        db_path = chatstorage_path(resolve_backup_dir(settings.ios_dir, request.backup_id))

    process = ProcessStatus(
        process_id=str(uuid.uuid4()),
        OS=request.platform,
        extraction_name_udid=request.backup_id,
        db_path=str(db_path),
        start_time=datetime.now(),
        status="Started",
        details="Process is started",
        date_from=request.date_from,
        date_to=request.date_to,
        received=request.received,
        sent=request.sent,
        contacts=",".join(request.contacts),
        groups=",".join(request.groups),
        msg_type=",".join(request.message_types),
        analyzers=",".join(request.analyzers),
        created_by=user.id,
    )
    with session_scope() as session:
        session.add(process)
        process_id = process.process_id

    dispatch_analysis(process_id)
    return AnalysisSubmitted(process_id=process_id, status="Started")


@router.get("", response_model=list[ProcessOut])
def list_analyses():
    with session_scope() as session:
        return [_to_process_out(p) for p in repositories.list_processes(session)]


@router.get("/{process_id}", response_model=ProcessOut)
def get_analysis(process_id: str):
    with session_scope() as session:
        process = repositories.get_process(session, process_id)
        if process is None:
            raise HTTPException(status_code=404, detail="Analysis process not found")
        return _to_process_out(process)


@router.get("/{process_id}/events")
def analysis_events(process_id: str):
    """Server-Sent Events stream of the process status (ends on completion)."""

    def event_stream():
        deadline = time.monotonic() + SSE_MAX_SECONDS
        while time.monotonic() < deadline:
            with session_scope() as session:
                process = repositories.get_process(session, process_id)
                if process is None:
                    yield 'event: error\ndata: {"detail": "Analysis process not found"}\n\n'
                    return
                snapshot = _to_process_out(process).model_dump(mode="json")
            yield f"data: {json.dumps(snapshot)}\n\n"
            if snapshot["status"] in ("Finish", "Error"):
                return
            time.sleep(SSE_POLL_SECONDS)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{process_id}/results", response_model=list[TextResultOut])
def get_analysis_results(process_id: str):
    with session_scope() as session:
        if repositories.get_process(session, process_id) is None:
            raise HTTPException(status_code=404, detail="Analysis process not found")
        return [
            TextResultOut(
                msg_id=text.msg_id,
                text=text.text,
                date=text.date,
                piis=[
                    FindingOut(
                        type=p.type,
                        value=p.value,
                        source=p.source,
                        analyzer_version=p.analyzer_version,
                        analyzer_digest=p.analyzer_digest,
                    )
                    for p in text.piis
                ],
                passwords=[
                    FindingOut(
                        value=p.password,
                        source=p.source,
                        analyzer_version=p.analyzer_version,
                        analyzer_digest=p.analyzer_digest,
                    )
                    for p in text.passwords
                ],
            )
            for text in repositories.get_texts_by_process(session, process_id)
        ]
