"""Application settings, loaded from environment variables (12-factor).

Every field can be set with an ``FW_``-prefixed environment variable
(e.g. ``FW_DATABASE_URL``); a local ``.env`` file is honored for development.
See ``.env.example`` at the repository root for the full reference.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Evidence storage -------------------------------------------------
    data_dir: Path = Path("data")
    ios_extractions_dir: Optional[Path] = None
    android_extractions_dir: Optional[Path] = None

    # Static assets used by report generation (logo, media-type icons) and
    # analyzer health checks (test audio/image files). Optional: reports are
    # generated without a logo when unset.
    assets_dir: Optional[Path] = None

    # WhatsApp schema registry: versioned descriptors + query packs.
    # Default resolves relative to the working directory (repo root in dev);
    # the Docker images set it to the bundled copy.
    schemas_dir: Path = Path("schemas/whatsapp")

    # --- Object storage (S3 / MinIO) ---------------------------------------
    # Durable store for backups uploaded through the projects API. Unset =
    # feature disabled. ``file://`` endpoints select the filesystem backend
    # (development and tests); anything else is treated as S3-compatible.
    s3_endpoint: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_bucket: str = "forensicwace-evidence"
    s3_region: Optional[str] = None

    # --- Authentication ------------------------------------------------------
    # JWT session cookie. Unset secret = ephemeral per-process (dev only:
    # sessions die on restart and cannot span replicas). FW_AUTH_DISABLED
    # turns the whole layer off (tests / trusted single-user labs).
    jwt_secret: Optional[str] = None
    auth_disabled: bool = False
    session_hours: int = 12
    cookie_secure: bool = False  # set true behind TLS
    admin_username: Optional[str] = None  # bootstrap admin, created at startup
    admin_password: Optional[str] = None

    # --- Results database (PostgreSQL) ------------------------------------
    database_url: Optional[str] = None

    # --- Message broker (RabbitMQ) -----------------------------------------
    # When set, analysis jobs are dispatched to the Celery workers; when
    # unset, the API falls back to an in-process background thread (dev mode).
    broker_url: Optional[str] = None

    # --- Report timestamping (RFC 3161) ------------------------------------
    tsa_url: str = "https://freetsa.org/tsr"
    tsa_certificate_file: Optional[Path] = None

    # --- Local analyzer services (Docker sidecars) -------------------------
    deeppass_endpoint: Optional[str] = None
    whisper_endpoint: Optional[str] = None
    tesseract_endpoint: Optional[str] = None
    lavis_endpoint: Optional[str] = None

    # --- Hugging Face (StarPII) --------------------------------------------
    hf_token: Optional[str] = None

    # --- OpenAI ------------------------------------------------------------
    openai_api_key: Optional[str] = None
    openai_assistant_id: Optional[str] = None

    # --- Microsoft Azure ----------------------------------------------------
    ms_pii_endpoint: Optional[str] = None
    ms_pii_key: Optional[str] = None
    ms_s2t_key: Optional[str] = None
    ms_s2t_region: Optional[str] = None
    ms_s2t_language: str = "en-US"
    ms_cv_endpoint: Optional[str] = None
    ms_cv_key: Optional[str] = None
    ms_cv_language: str = "en"

    # --- Pay-to-use analyzer toggles ----------------------------------------
    use_ms_s2t: bool = False
    use_ms_ocr_caption: bool = False
    use_ms_pii: bool = False
    use_openai_gpt: bool = False

    # --- Presidio -------------------------------------------------------------
    presidio_recognizers_file: Optional[Path] = None

    @property
    def ios_dir(self) -> Path:
        return self.ios_extractions_dir or self.data_dir / "device_extractions_IOS"

    @property
    def android_dir(self) -> Path:
        return self.android_extractions_dir or self.data_dir / "device_extractions_Android"

    @property
    def staging_dir(self) -> Path:
        """Scratch area for uploads in transit; outside the extraction roots
        so partially processed archives never show up as backups."""
        return self.data_dir / "staging"

    def extraction_root(self, platform: str) -> Path:
        return self.ios_dir if platform == "ios" else self.android_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    """Reset cached settings (used by tests that tweak the environment)."""
    get_settings.cache_clear()
