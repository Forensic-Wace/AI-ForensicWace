"""Discovery of Android WhatsApp extractions (msgstore.db + optional Media/)."""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..exceptions import BackupNotFoundError
from ..utils.hashing import file_size_mb, md5_of, sha256_of
from .ios import validate_identifier


@dataclass
class AndroidBackupInfo:
    folder: str
    db_file: str
    size_mb: float | None
    created_at: datetime | None


def resolve_backup_dir(root: Path, folder: str) -> Path:
    backup_dir = root / validate_identifier(folder)
    if not backup_dir.is_dir():
        raise BackupNotFoundError(f"Android extraction {folder!r} not found")
    return backup_dir


def resolve_db_path(root: Path, folder: str, db_file: str = "msgstore.db") -> Path:
    validate_identifier(db_file)
    db_path = resolve_backup_dir(root, folder) / db_file
    if not db_path.is_file() or db_path.suffix != ".db":
        raise BackupNotFoundError(f"Database {db_file!r} not found in extraction {folder!r}")
    return db_path


def list_backups(root: Path) -> list[AndroidBackupInfo]:
    """All ``.db`` files found in the first-level folders of the extraction root."""
    if not root.is_dir():
        return []
    backups = []
    for entry in sorted(os.scandir(root), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        for file in sorted(os.listdir(entry.path)):
            if file.endswith(".db"):
                path = Path(entry.path) / file
                backups.append(
                    AndroidBackupInfo(
                        folder=entry.name,
                        db_file=file,
                        size_mb=file_size_mb(path),
                        created_at=datetime.fromtimestamp(path.stat().st_ctime, timezone.utc),
                    )
                )
    return backups


def database_fingerprint(db_path: Path) -> dict:
    return {
        "sha256": sha256_of(db_path),
        "md5": md5_of(db_path),
        "size_mb": file_size_mb(db_path),
    }
