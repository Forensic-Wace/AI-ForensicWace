"""Object storage for uploaded evidence (S3/MinIO, or filesystem in dev).

The backend is selected by ``FW_S3_ENDPOINT``: unset disables the feature,
``file://`` roots a local directory, anything else is S3-compatible.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from ..config import get_settings
from ..exceptions import ConfigurationError
from .base import ObjectStorage
from .local import LocalObjectStorage
from .s3 import S3ObjectStorage

__all__ = ["ObjectStorage", "LocalObjectStorage", "S3ObjectStorage", "get_object_storage", "clear_storage_cache"]


@lru_cache
def get_object_storage() -> ObjectStorage:
    """Configured storage backend; raises ConfigurationError when unset."""
    settings = get_settings()
    endpoint = settings.s3_endpoint
    if not endpoint:
        raise ConfigurationError("FW_S3_ENDPOINT is not configured — object storage is unavailable")

    parsed = urlparse(endpoint)
    if parsed.scheme == "file":
        # url2pathname handles Windows drive letters in file:///C:/... URLs
        return LocalObjectStorage(Path(url2pathname(parsed.path)) / settings.s3_bucket)

    if not settings.s3_access_key or not settings.s3_secret_key:
        raise ConfigurationError("FW_S3_ACCESS_KEY / FW_S3_SECRET_KEY are required for S3 object storage")
    storage = S3ObjectStorage(
        endpoint=endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
    )
    storage.ensure_bucket()
    return storage


def clear_storage_cache() -> None:
    """Reset the cached backend (used by tests that tweak the environment)."""
    get_object_storage.cache_clear()
