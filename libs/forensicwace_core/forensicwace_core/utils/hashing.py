"""File hashing and size helpers used for evidence integrity."""

import hashlib
import os
from pathlib import Path

_CHUNK = 1024 * 1024


def _digest(path: Path | str, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def sha256_of(path: Path | str) -> str:
    return _digest(path, "sha256")


def md5_of(path: Path | str) -> str:
    return _digest(path, "md5")


def file_size_mb(path: Path | str) -> float | None:
    """File size in megabytes, or None when the file does not exist."""
    try:
        return round(os.path.getsize(path) / (1024 * 1024), 3)
    except OSError:
        return None
