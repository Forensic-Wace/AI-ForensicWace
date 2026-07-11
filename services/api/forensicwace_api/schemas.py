"""Request/response models of the public API."""

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)


class MeOut(BaseModel):
    id: int | None = None
    username: str
    role: str
    auth_disabled: bool = False


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(min_length=8)
    role: str = Field(default="analyst", pattern="^(admin|analyst)$")


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|analyst)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime | None = None
    last_login: datetime | None = None


class AuditEntryOut(BaseModel):
    id: int
    at: datetime
    user_id: int | None = None
    username: str | None = None
    action: str
    resource: str | None = None
    detail: str | None = None


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


class InstalledAnalyzerOut(BaseModel):
    key: str
    name: str
    version: str
    type: str  # builtin | http
    capabilities: list[str]
    input: str  # text | audio | image
    trust: str  # local | cloud
    enabled: bool
    endpoint: str | None = None
    image_digest: str | None = None
    config: dict = {}


class AnalyzerRegister(BaseModel):
    """Bring-your-own-container registration: the manifest is fetched from
    the endpoint and is authoritative for key/name/capabilities."""

    endpoint: str = Field(min_length=1, description="Base URL of a fw-analyzer/1 container")
    config: dict = {}
    enabled: bool = True


class AnalyzerUpdate(BaseModel):
    enabled: bool | None = None
    config: dict | None = None


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
    total_messages: int = 0
    analyzed_messages: int = 0
    failed_messages: int = 0


class FindingOut(BaseModel):
    type: str | None = None
    value: str | None = None
    source: str
    # provenance: exact analyzer build (chain of custody)
    analyzer_version: str | None = None
    analyzer_digest: str | None = None


class TextResultOut(BaseModel):
    msg_id: str
    text: str
    date: datetime | None = None
    piis: list[FindingOut] = []
    passwords: list[FindingOut] = []


class ReportVerification(BaseModel):
    verified: bool


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class ProjectBackupOut(BaseModel):
    id: str
    platform: str
    identifier: str
    status: str
    detail: str | None = None
    original_filename: str | None = None
    size_bytes: int = 0
    file_count: int = 0
    uploaded_at: datetime | None = None
    completed_at: datetime | None = None
    # computed: a working copy exists in the local extraction root
    hydrated: bool = False


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: datetime | None = None
    backup_count: int = 0


class ProjectDetailOut(ProjectOut):
    backups: list[ProjectBackupOut] = []
