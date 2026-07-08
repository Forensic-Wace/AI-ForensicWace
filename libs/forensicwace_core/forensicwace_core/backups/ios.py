"""Discovery of iOS device backups (iTunes-style, unencrypted)."""

import os
import plistlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..constants import IOS_CHATSTORAGE_RELATIVE_PATH, IOS_MANIFEST_DB, IOS_MANIFEST_PLIST
from ..exceptions import BackupNotFoundError, InvalidIdentifierError
from ..utils.hashing import file_size_mb, md5_of, sha256_of


@dataclass
class IosBackupInfo:
    udid: str
    device_name: str | None
    ios_version: str | None
    serial_number: str | None
    device_type: str | None
    backup_date: datetime | None


def validate_identifier(identifier: str) -> str:
    """Reject identifiers that could escape the extraction root."""
    if not identifier or identifier != os.path.basename(identifier) or identifier in (".", ".."):
        raise InvalidIdentifierError(f"Invalid backup identifier: {identifier!r}")
    return identifier


def resolve_backup_dir(root: Path, udid: str) -> Path:
    backup_dir = root / validate_identifier(udid)
    if not backup_dir.is_dir():
        raise BackupNotFoundError(f"iOS backup {udid!r} not found")
    return backup_dir


def chatstorage_path(backup_dir: Path) -> Path:
    return backup_dir.joinpath(*IOS_CHATSTORAGE_RELATIVE_PATH)


def manifest_db_path(backup_dir: Path) -> Path:
    return backup_dir / IOS_MANIFEST_DB


def read_backup_info(root: Path, udid: str) -> IosBackupInfo | None:
    """Read device metadata from Manifest.plist; None when the manifest is missing."""
    backup_dir = resolve_backup_dir(root, udid)
    manifest_file = backup_dir / IOS_MANIFEST_PLIST
    try:
        with open(manifest_file, "rb") as f:
            manifest = plistlib.load(f)
    except (FileNotFoundError, plistlib.InvalidFileException):
        return None

    lockdown = manifest.get("Lockdown", {})
    return IosBackupInfo(
        udid=udid,
        device_name=lockdown.get("DeviceName"),
        ios_version=lockdown.get("ProductVersion"),
        serial_number=lockdown.get("SerialNumber"),
        device_type=lockdown.get("ProductType"),
        backup_date=datetime.fromtimestamp(manifest_file.stat().st_mtime, timezone.utc),
    )


def list_backups(root: Path) -> list[IosBackupInfo]:
    """All valid iOS backups under the extraction root."""
    if not root.is_dir():
        return []
    backups = []
    for entry in sorted(os.scandir(root), key=lambda e: e.name):
        if entry.is_dir():
            info = read_backup_info(root, entry.name)
            if info is not None:
                backups.append(info)
    return backups


def database_fingerprint(backup_dir: Path) -> dict:
    """Integrity data (hashes, size) of the ChatStorage database."""
    db_path = chatstorage_path(backup_dir)
    if not db_path.is_file():
        raise BackupNotFoundError(f"ChatStorage.sqlite not found in backup {backup_dir.name!r}")
    return {
        "sha256": sha256_of(db_path),
        "md5": md5_of(db_path),
        "size_mb": file_size_mb(db_path),
    }
