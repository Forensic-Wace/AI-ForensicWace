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


class ProvidersOut(BaseModel):
    """Login methods available to the login page."""

    password: bool = True
    oidc: bool = False


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
    # required true when the container's manifest declares trust=cloud
    consent: bool = False


class AnalyzerUpdate(BaseModel):
    enabled: bool | None = None
    config: dict | None = None


class CatalogEntryOut(BaseModel):
    key: str
    name: str
    version: str
    capabilities: list[str]
    input: str
    trust: str  # local | cloud
    gpu: bool = False
    config_schema: dict = {}
    image: str
    image_digest: str
    port: int
    description: str = ""
    publisher: str = ""
    homepage: str = ""
    installed: bool = False
    installed_version: str | None = None


class CatalogOut(BaseModel):
    name: str = ""
    # signature verified against the pinned FW_CATALOG_PUBLIC_KEY
    verified: bool = False
    # a runtime provisioner is configured: installs need no manual endpoint
    provisioner: bool = False
    entries: list[CatalogEntryOut] = []


class MarketplaceInstall(BaseModel):
    """Install request. ``endpoint`` is required when no provisioner is
    configured; ``consent`` must be true for trust=cloud analyzers."""

    endpoint: str | None = None
    config: dict = {}
    consent: bool = False


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


class ProjectMemberAdd(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class ProjectMemberOut(BaseModel):
    user_id: int
    username: str | None = None
    added_at: datetime | None = None


class ProjectDetailOut(ProjectOut):
    backups: list[ProjectBackupOut] = []
    owner: str | None = None
    # computed for the requesting operator: may share/delete this case
    can_manage: bool = True
    members: list[ProjectMemberOut] = []
