"""Backup discovery and evidence integrity."""

from dataclasses import asdict

from fastapi import APIRouter

from forensicwace_core.backups import android, ios
from forensicwace_core.config import get_settings

from ..schemas import AndroidBackup, DatabaseFingerprint, IosBackup

router = APIRouter(prefix="/backups", tags=["backups"])


@router.get("/ios", response_model=list[IosBackup])
def list_ios_backups():
    return [asdict(b) for b in ios.list_backups(get_settings().ios_dir)]


@router.get("/android", response_model=list[AndroidBackup])
def list_android_backups():
    return [asdict(b) for b in android.list_backups(get_settings().android_dir)]


@router.get("/ios/{udid}")
def ios_backup_detail(udid: str):
    settings = get_settings()
    backup_dir = ios.resolve_backup_dir(settings.ios_dir, udid)
    info = ios.read_backup_info(settings.ios_dir, udid)
    return {
        "info": asdict(info) if info else None,
        "database": DatabaseFingerprint(**ios.database_fingerprint(backup_dir)),
    }


@router.get("/android/{folder}")
def android_backup_detail(folder: str, db: str = "msgstore.db"):
    db_path = android.resolve_db_path(get_settings().android_dir, folder, db)
    return {
        "folder": folder,
        "db_file": db,
        "database": DatabaseFingerprint(**android.database_fingerprint(db_path)),
    }
