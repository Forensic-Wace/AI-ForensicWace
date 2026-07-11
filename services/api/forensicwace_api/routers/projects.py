"""Project (case) management: browser uploads of backups into object storage.

A project groups backups uploaded as ZIP archives. Each upload is staged to
disk, validated, then mirrored to S3/MinIO — the durable evidence store —
and hydrated into the local extraction roots, where every existing endpoint
(chats, exports, AI analyses) picks it up unchanged. Requires both
``FW_DATABASE_URL`` and ``FW_S3_ENDPOINT``; endpoints answer 503 otherwise.

Mirroring runs as a FastAPI background task in the API process: the archive
is already on the API's staging disk, so unlike analyses it is not routed
through the Celery workers. Clients poll the backup status ("processing" ->
"hydrating" -> "stored" | "error").
"""

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from forensicwace_core.backups import packaging
from forensicwace_core.backups.ios import validate_identifier
from forensicwace_core.config import get_settings
from forensicwace_core.constants import Platform
from forensicwace_core.resultsdb import repositories
from forensicwace_core.resultsdb.engine import session_scope
from forensicwace_core.resultsdb.models import Project, ProjectBackup, ProjectMember, User
from forensicwace_core.storage import get_object_storage

from .. import audit
from ..auth import AuthUser, get_current_user
from ..schemas import (
    ProjectBackupOut,
    ProjectCreate,
    ProjectDetailOut,
    ProjectMemberAdd,
    ProjectMemberOut,
    ProjectOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_backup_out(backup: ProjectBackup) -> ProjectBackupOut:
    local_dir = get_settings().extraction_root(backup.platform) / backup.identifier
    return ProjectBackupOut(
        id=backup.id,
        platform=backup.platform,
        identifier=backup.identifier,
        status=backup.status,
        detail=backup.detail,
        original_filename=backup.original_filename,
        size_bytes=backup.size_bytes or 0,
        file_count=backup.file_count or 0,
        uploaded_at=backup.uploaded_at,
        completed_at=backup.completed_at,
        hydrated=local_dir.is_dir(),
    )


def _to_project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        backup_count=len(project.backups),
    )


def _is_admin(user: AuthUser) -> bool:
    return user.role == "admin"


def _accessible_project(session, project_id: str, user: AuthUser) -> Project:
    """The project, if the operator may see it. Non-members get the same 404
    as a nonexistent case: the ACL also hides existence."""
    project = repositories.get_project(session, project_id)
    if project is None or not repositories.can_access_project(project, user.id, _is_admin(user)):
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _manageable_project(session, project_id: str, user: AuthUser) -> Project:
    project = _accessible_project(session, project_id, user)
    if not repositories.can_manage_project(project, user.id, _is_admin(user)):
        raise HTTPException(status_code=403, detail="Only the case owner or an admin can do this")
    return project


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(request: ProjectCreate, user: AuthUser = Depends(get_current_user)):
    project = Project(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        created_at=_now(),
        created_by=user.id,
    )
    with session_scope() as session:
        session.add(project)
        session.flush()
        out = _to_project_out(project)
    audit.record(user, "project.created", resource=request.name)
    return out


@router.get("", response_model=list[ProjectOut])
def list_projects(user: AuthUser = Depends(get_current_user)):
    with session_scope() as session:
        return [
            _to_project_out(p)
            for p in repositories.list_projects(session)
            if repositories.can_access_project(p, user.id, _is_admin(user))
        ]


@router.get("/{project_id}", response_model=ProjectDetailOut)
def project_detail(project_id: str, user: AuthUser = Depends(get_current_user)):
    with session_scope() as session:
        project = _accessible_project(session, project_id, user)
        names = repositories.usernames_by_id(
            session, [m.user_id for m in project.members] + ([project.created_by] if project.created_by else [])
        )
        return ProjectDetailOut(
            **_to_project_out(project).model_dump(),
            backups=[_to_backup_out(b) for b in project.backups],
            owner=names.get(project.created_by),
            can_manage=repositories.can_manage_project(project, user.id, _is_admin(user)),
            members=[
                ProjectMemberOut(user_id=m.user_id, username=names.get(m.user_id), added_at=m.added_at)
                for m in project.members
            ],
        )


@router.post("/{project_id}/members", response_model=ProjectMemberOut, status_code=201)
def add_member(project_id: str, request: ProjectMemberAdd, user: AuthUser = Depends(get_current_user)):
    """Share the case with another operator (owner or admin only)."""
    with session_scope() as session:
        project = _manageable_project(session, project_id, user)
        target = session.query(User).filter(User.username == request.username).first()
        if target is None or not target.is_active:
            raise HTTPException(status_code=404, detail=f"No active user named {request.username!r}")
        if target.id == project.created_by:
            raise HTTPException(status_code=409, detail="That user owns this case")
        if any(m.user_id == target.id for m in project.members):
            raise HTTPException(status_code=409, detail="Case is already shared with that user")
        member = ProjectMember(project_id=project.id, user_id=target.id, added_at=_now(), added_by=user.id)
        session.add(member)
        session.flush()
        out = ProjectMemberOut(user_id=member.user_id, username=target.username, added_at=member.added_at)
        name = project.name
    audit.record(user, "project.shared", resource=name, detail=f"with={request.username}")
    return out


@router.delete("/{project_id}/members/{member_user_id}", status_code=204)
def remove_member(project_id: str, member_user_id: int, user: AuthUser = Depends(get_current_user)):
    with session_scope() as session:
        project = _manageable_project(session, project_id, user)
        member = next((m for m in project.members if m.user_id == member_user_id), None)
        if member is None:
            raise HTTPException(status_code=404, detail="Case is not shared with that user")
        username = repositories.usernames_by_id(session, [member_user_id]).get(member_user_id, member_user_id)
        session.delete(member)
        name = project.name
    audit.record(user, "project.unshared", resource=name, detail=f"with={username}")


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, user: AuthUser = Depends(get_current_user)):
    """Remove the project: database records and every object under its
    storage prefix. Hydrated working copies in the extraction roots are kept."""
    with session_scope() as session:
        project = _manageable_project(session, project_id, user)
        had_backups = bool(project.backups)
        name = project.name
        session.delete(project)
    if had_backups:
        get_object_storage().delete_prefix(f"projects/{project_id}/")
    audit.record(user, "project.deleted", resource=name, detail=f"backups_removed={had_backups}")


@router.post("/{project_id}/backups", response_model=ProjectBackupOut, status_code=202)
def upload_backup(
    project_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(..., description="ZIP archive of the backup/extraction folder"),
    platform: Platform = Form(...),
    identifier: str | None = Form(None, description="Target folder/UDID name; defaults to the archive name"),
    auto_hydrate: bool = Form(True, description="Also materialize a local working copy right away"),
    user: AuthUser = Depends(get_current_user),
):
    settings = get_settings()
    get_object_storage()  # fail fast (503) before accepting the body
    identifier = validate_identifier(identifier or Path(file.filename or "").stem or str(uuid.uuid4()))

    backup_id = str(uuid.uuid4())
    with session_scope() as session:
        _accessible_project(session, project_id, user)
        existing = repositories.find_backup_by_identity(session, platform.value, identifier)
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"A backup named {identifier!r} was already uploaded")
    if (settings.extraction_root(platform.value) / identifier).exists():
        raise HTTPException(
            status_code=409,
            detail=f"{identifier!r} already exists in the local extraction root — pick another identifier",
        )

    settings.staging_dir.mkdir(parents=True, exist_ok=True)
    staging_path = settings.staging_dir / f"{backup_id}.zip"
    try:
        with staging_path.open("wb") as dest:
            shutil.copyfileobj(file.file, dest)
        inventory = packaging.inspect_archive(staging_path, platform.value)  # 422 on junk
    except Exception:
        staging_path.unlink(missing_ok=True)
        raise

    backup = ProjectBackup(
        id=backup_id,
        project_id=project_id,
        platform=platform.value,
        identifier=identifier,
        status="processing",
        detail=f"Mirroring {inventory.file_count} files to object storage",
        object_prefix=packaging.object_prefix(project_id, platform.value, identifier),
        original_filename=file.filename,
        size_bytes=inventory.total_bytes,
        file_count=inventory.file_count,
        uploaded_at=_now(),
        created_by=user.id,
    )
    with session_scope() as session:
        session.add(backup)
        session.flush()
        out = _to_backup_out(backup)

    background.add_task(_process_upload, backup_id, staging_path, auto_hydrate)
    audit.record(
        user, "backup.uploaded", resource=f"{platform.value}/{identifier}",
        detail=f"project={project_id} files={inventory.file_count} bytes={inventory.total_bytes}",
    )
    return out


@router.get("/{project_id}/backups/{backup_id}", response_model=ProjectBackupOut)
def backup_status(project_id: str, backup_id: str, user: AuthUser = Depends(get_current_user)):
    with session_scope() as session:
        _accessible_project(session, project_id, user)
        backup = repositories.get_project_backup(session, project_id, backup_id)
        if backup is None:
            raise HTTPException(status_code=404, detail="Backup not found in this project")
        return _to_backup_out(backup)


@router.post("/{project_id}/backups/{backup_id}/hydrate", response_model=ProjectBackupOut, status_code=202)
def hydrate_backup(project_id: str, backup_id: str, background: BackgroundTasks, user: AuthUser = Depends(get_current_user)):
    """Materialize a working copy from object storage into the extraction
    root (e.g. after the local volume was wiped or on another node)."""
    get_object_storage()
    with session_scope() as session:
        _accessible_project(session, project_id, user)
        backup = repositories.get_project_backup(session, project_id, backup_id)
        if backup is None:
            raise HTTPException(status_code=404, detail="Backup not found in this project")
        if backup.status != "stored":
            raise HTTPException(status_code=409, detail=f"Backup is {backup.status} — wait for it to be stored")
        backup.status = "hydrating"
        backup.detail = "Downloading working copy from object storage"
        out = _to_backup_out(backup)

    background.add_task(_hydrate_from_storage, backup_id)
    audit.record(user, "backup.hydrated", resource=f"{out.platform}/{out.identifier}", detail=f"project={project_id}")
    return out


@router.delete("/{project_id}/backups/{backup_id}", status_code=204)
def delete_backup(project_id: str, backup_id: str, purge_local: bool = False, user: AuthUser = Depends(get_current_user)):
    """Remove the backup from object storage and the project. The hydrated
    working copy is kept unless ``purge_local`` is set."""
    with session_scope() as session:
        _accessible_project(session, project_id, user)
        backup = repositories.get_project_backup(session, project_id, backup_id)
        if backup is None:
            raise HTTPException(status_code=404, detail="Backup not found in this project")
        prefix, platform, identifier = backup.object_prefix, backup.platform, backup.identifier
        session.delete(backup)
    get_object_storage().delete_prefix(prefix)
    if purge_local:
        local_dir = get_settings().extraction_root(platform) / identifier
        if local_dir.is_dir():
            shutil.rmtree(local_dir)
    audit.record(user, "backup.deleted", resource=f"{platform}/{identifier}", detail=f"project={project_id} purge_local={purge_local}")


# --- Background steps -------------------------------------------------------


def _set_backup_state(backup_id: str, **fields) -> ProjectBackup | None:
    with session_scope() as session:
        backup = session.query(ProjectBackup).filter_by(id=backup_id).first()
        if backup is None:  # backup deleted mid-flight
            return None
        for name, value in fields.items():
            setattr(backup, name, value)
        session.flush()
        session.expunge(backup)
        return backup


def _materialize_local_copy(backup: ProjectBackup, source_zip: Path | None) -> None:
    """Extract (or download) into a temp dir outside the extraction roots,
    then move into place so listings never see a half-written backup."""
    settings = get_settings()
    final_dir = settings.extraction_root(backup.platform) / backup.identifier
    if final_dir.exists():
        return
    temp_dir = settings.staging_dir / f"hydrate-{backup.id}"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    try:
        if source_zip is not None:
            packaging.extract_to_dir(source_zip, temp_dir)
        else:
            packaging.hydrate_from_storage(get_object_storage(), backup.object_prefix, temp_dir)
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_dir), str(final_dir))
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def _process_upload(backup_id: str, staging_path: Path, auto_hydrate: bool) -> None:
    try:
        backup = _set_backup_state(backup_id, detail="Mirroring to object storage")
        if backup is None:
            return
        inventory = packaging.mirror_to_storage(get_object_storage(), backup.object_prefix, staging_path)
        if auto_hydrate:
            backup = _set_backup_state(backup_id, status="hydrating", detail="Extracting local working copy")
            if backup is None:
                return
            _materialize_local_copy(backup, source_zip=staging_path)
        _set_backup_state(
            backup_id,
            status="stored",
            detail="",
            size_bytes=inventory.total_bytes,
            file_count=inventory.file_count,
            completed_at=_now(),
        )
    except Exception as exc:
        logger.exception("Upload processing failed for backup %s", backup_id)
        _set_backup_state(backup_id, status="error", detail=str(exc), completed_at=_now())
    finally:
        staging_path.unlink(missing_ok=True)


def _hydrate_from_storage(backup_id: str) -> None:
    try:
        backup = _set_backup_state(backup_id, detail="Downloading working copy from object storage")
        if backup is None:
            return
        _materialize_local_copy(backup, source_zip=None)
        _set_backup_state(backup_id, status="stored", detail="")
    except Exception as exc:
        # still safely stored in the bucket: report the failure, keep status
        logger.exception("Hydration failed for backup %s", backup_id)
        _set_backup_state(backup_id, status="stored", detail=f"Hydration failed: {exc}")
