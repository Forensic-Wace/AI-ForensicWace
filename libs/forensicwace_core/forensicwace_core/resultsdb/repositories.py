"""Query helpers for analysis results. All functions take an active session."""

from sqlalchemy.orm import Session, selectinload

from .models import ProcessStatus, Text


def get_process(session: Session, process_id: str) -> ProcessStatus | None:
    return session.query(ProcessStatus).filter_by(process_id=process_id).first()


def list_processes(session: Session) -> list[ProcessStatus]:
    return session.query(ProcessStatus).order_by(ProcessStatus.start_time.desc()).all()


def get_texts_by_process(session: Session, process_id: str) -> list[Text]:
    return (
        session.query(Text)
        .options(selectinload(Text.piis), selectinload(Text.passwords))
        .filter(Text.process_id == process_id)
        .all()
    )
