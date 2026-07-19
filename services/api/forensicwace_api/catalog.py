"""The analyzer catalog (marketplace phase B): a signed index of installable
fw-analyzer/1 containers.

The catalog is a ``fw-catalog/1`` JSON document reached over http(s) or
``file://`` (FW_CATALOG_URL). Every entry embeds the analyzer manifest plus
the container image **pinned to a sha256 digest** — tags are rejected at the
model level, per the marketplace security requirements.

Authenticity: when ``FW_CATALOG_PUBLIC_KEY`` is configured (base64 raw
Ed25519 public key), the detached signature published at ``<url>.sig``
(base64) is required and verified over the exact catalog bytes. Without a
configured key the catalog still loads but is reported — and displayed — as
unverified. ``tools/sign_catalog.py`` generates keys and signatures.
"""

import base64
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlsplit, urlunsplit
from urllib.request import url2pathname

import httpx
from pydantic import BaseModel, Field, ValidationError

from forensicwace_core.analysis.contract import AnalyzerManifest
from forensicwace_core.config import get_settings
from forensicwace_core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

CATALOG_FORMAT = "fw-catalog/1"
CACHE_TTL_SECONDS = 60.0

# injectable for tests (httpx.MockTransport)
_transport: httpx.BaseTransport | None = None


class CatalogError(Exception):
    """The catalog could not be fetched, parsed or verified."""


class CatalogEntry(BaseModel):
    manifest: AnalyzerManifest
    image: str = Field(
        pattern=r"^[^\s@]+@sha256:[0-9a-f]{64}$",
        description="Container image pinned to a sha256 digest (tags are not installable)",
    )
    port: int = Field(default=9300, ge=1, le=65535)
    # static environment injected at provision time (e.g. the shim's
    # FW_SHIM_TARGET). Values are catalog data: never secrets.
    env: dict[str, str] = {}
    description: str = ""
    publisher: str = ""
    homepage: str = ""

    @property
    def image_digest(self) -> str:
        return self.image.rsplit("@", 1)[1]


class Catalog(BaseModel):
    format: Literal["fw-catalog/1"]
    name: str = ""
    entries: list[CatalogEntry] = []

    def by_key(self) -> dict[str, CatalogEntry]:
        return {entry.manifest.key: entry for entry in self.entries}


@dataclass(frozen=True)
class LoadedCatalog:
    catalog: Catalog
    verified: bool  # signature checked against FW_CATALOG_PUBLIC_KEY


_cache_lock = threading.Lock()
_cache: tuple[float, LoadedCatalog] | None = None


def _read(url: str) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme == "file":
        # keep relative forms working: file:catalog/x.json and
        # file://./catalog/x.json both resolve against the working directory
        netloc = "" if parsed.netloc in ("", "localhost") else parsed.netloc
        return Path(url2pathname(netloc + parsed.path)).read_bytes()
    if parsed.scheme in ("http", "https"):
        with httpx.Client(transport=_transport, timeout=15) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content
    raise CatalogError(f"Unsupported catalog URL scheme: {parsed.scheme!r}")


def _sig_url(url: str) -> str:
    """The detached-signature URL: ``.sig`` on the path, before any query
    (presigned/tokenized catalog URLs keep working)."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=parts.path + ".sig"))


def _verify_signature(payload: bytes, signature_b64: bytes, public_key_b64: str) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    except Exception as exc:
        raise CatalogError(f"FW_CATALOG_PUBLIC_KEY is not a base64 Ed25519 public key: {exc}")
    try:
        public_key.verify(base64.b64decode(signature_b64.strip()), payload)
    except (InvalidSignature, ValueError) as exc:
        raise CatalogError(f"Catalog signature verification FAILED: {exc or 'invalid signature'}")


def load_catalog(force_refresh: bool = False) -> LoadedCatalog:
    """The configured catalog, verified when a public key is pinned.

    Raises ConfigurationError (503) when no catalog is configured and
    CatalogError when it cannot be fetched, parsed or verified.
    """
    global _cache
    settings = get_settings()
    if not settings.catalog_url:
        raise ConfigurationError("FW_CATALOG_URL is not set — the analyzer marketplace is disabled")

    with _cache_lock:
        if not force_refresh and _cache is not None and time.monotonic() - _cache[0] < CACHE_TTL_SECONDS:
            return _cache[1]

    # The configured URL may carry access tokens: log it for the operator,
    # but never echo it into error details shown to every analyst.
    try:
        raw = _read(settings.catalog_url)
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("Cannot fetch catalog %s: %s", settings.catalog_url, exc)
        raise CatalogError(f"Cannot fetch the configured catalog ({exc.__class__.__name__})")

    verified = False
    if settings.catalog_public_key:
        try:
            signature = _read(_sig_url(settings.catalog_url))
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Cannot fetch catalog signature for %s: %s", settings.catalog_url, exc)
            raise CatalogError(
                f"The catalog signature (.sig) is required but unreadable ({exc.__class__.__name__})"
            )
        _verify_signature(raw, signature, settings.catalog_public_key)
        verified = True

    try:
        catalog = Catalog.model_validate_json(raw)
    except ValidationError as exc:
        raise CatalogError(f"Catalog does not conform to {CATALOG_FORMAT}: {exc}")

    loaded = LoadedCatalog(catalog=catalog, verified=verified)
    with _cache_lock:
        _cache = (time.monotonic(), loaded)
    return loaded


def entry_for(key: str) -> Optional[CatalogEntry]:
    return load_catalog().catalog.by_key().get(key)


def clear_catalog_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None
