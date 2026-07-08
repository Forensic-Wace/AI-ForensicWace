"""Request/response models of the public API."""

from datetime import datetime

from pydantic import BaseModel, Field


class IosBackup(BaseModel):
    udid: str
    device_name: str | None = None
    ios_version: str | None = None
    serial_number: str | None = None
    device_type: str | None = None
    backup_date: datetime | None = None


class AndroidBackup(BaseModel):
    folder: str
    db_file: str
    size_mb: float | None = None
    created_at: datetime | None = None


class DatabaseFingerprint(BaseModel):
    sha256: str
    md5: str
    size_mb: float | None = None


class AnalyzerStatusOut(BaseModel):
    name: str
    available: bool
    detail: str = ""


class PrivateChatOut(BaseModel):
    counters: dict
    messages: list[dict]


class AnalysisRequest(BaseModel):
    platform: str = Field(pattern="^(ios|android)$")
    backup_id: str
    db_file: str = "msgstore.db"  # Android only
    date_from: datetime | None = None
    date_to: datetime | None = None
    received: bool = True
    sent: bool = True
    contacts: list[str] = []
    groups: list[str] = []
    message_types: list[str] = []
    analyzers: list[str] = []


class AnalysisSubmitted(BaseModel):
    process_id: str
    status: str


class ProcessOut(BaseModel):
    process_id: str
    platform: str | None = None
    backup_id: str | None = None
    status: str | None = None
    details: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    analyzers: list[str] = []


class FindingOut(BaseModel):
    type: str | None = None
    value: str | None = None
    source: str


class TextResultOut(BaseModel):
    msg_id: str
    text: str
    date: datetime | None = None
    piis: list[FindingOut] = []
    passwords: list[FindingOut] = []


class ReportVerification(BaseModel):
    verified: bool
