"""Query helpers for analysis results and projects. All functions take an active session."""

from sqlalchemy.orm import Session, selectinload

from .models import ProcessStatus, Project, ProjectBackup, Text


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


def list_projects(session: Session) -> list[Project]:
    return (
        session.query(Project)
        .options(selectinload(Project.backups))
        .order_by(Project.created_at.desc())
        .all()
    )


def get_project(session: Session, project_id: str) -> Project | None:
    return (
        session.query(Project)
        .options(selectinload(Project.backups))
        .filter_by(id=project_id)
        .first()
    )


def get_project_backup(session: Session, project_id: str, backup_id: str) -> ProjectBackup | None:
    return session.query(ProjectBackup).filter_by(id=backup_id, project_id=project_id).first()


def find_backup_by_identity(session: Session, platform: str, identifier: str) -> ProjectBackup | None:
    return session.query(ProjectBackup).filter_by(platform=platform, identifier=identifier).first()
