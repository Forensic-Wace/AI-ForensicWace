"""Object-storage interface used by the projects feature.

Keys are ``/``-separated POSIX-style paths (``projects/<id>/ios/<udid>/...``).
Implementations must be safe to share across threads.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO


class ObjectStorage(ABC):
    @abstractmethod
    def put_fileobj(self, key: str, fileobj: BinaryIO) -> None:
        """Store a readable binary stream under ``key`` (overwrites)."""

    @abstractmethod
    def get_file(self, key: str, dest: Path) -> None:
        """Download ``key`` to ``dest``, creating parent directories."""

    @abstractmethod
    def iter_keys(self, prefix: str) -> Iterator[str]:
        """All keys starting with ``prefix``."""

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """Delete every key under ``prefix``; returns the number removed."""
