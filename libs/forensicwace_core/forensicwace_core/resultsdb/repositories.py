"""Query helpers for analysis results and projects. All functions take an active session."""

from sqlalchemy.orm import Session, selectinload

from .models import ProcessStatus, Project, ProjectBackup, Text, User


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
        .options(selectinload(Project.backups), selectinload(Project.members))
        .order_by(Project.created_at.desc())
        .all()
    )


def get_project(session: Session, project_id: str) -> Project | None:
    return (
        session.query(Project)
        .options(selectinload(Project.backups), selectinload(Project.members))
        .filter_by(id=project_id)
        .first()
    )


def can_access_project(project: Project, user_id: int | None, is_admin: bool) -> bool:
    """Case visibility rule: admins (and auth-disabled mode, user_id None) see
    everything; projects predating the ACL (owner NULL) stay visible to all;
    otherwise access is owner or member."""
    if is_admin or user_id is None or project.created_by is None:
        return True
    return project.created_by == user_id or any(m.user_id == user_id for m in project.members)


def can_manage_project(project: Project, user_id: int | None, is_admin: bool) -> bool:
    """Sharing/deletion is reserved to the owner and admins."""
    if is_admin or user_id is None or project.created_by is None:
        return True
    return project.created_by == user_id


def usernames_by_id(session: Session, user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = session.query(User.id, User.username).filter(User.id.in_(set(user_ids))).all()
    return {row.id: row.username for row in rows if row.username}


def get_project_backup(session: Session, project_id: str, backup_id: str) -> ProjectBackup | None:
    return session.query(ProjectBackup).filter_by(id=backup_id, project_id=project_id).first()


def find_backup_by_identity(session: Session, platform: str, identifier: str) -> ProjectBackup | None:
    return session.query(ProjectBackup).filter_by(platform=platform, identifier=identifier).first()
