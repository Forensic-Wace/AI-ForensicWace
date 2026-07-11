"""Filesystem backend: ``FW_S3_ENDPOINT=file:///path`` (development, tests).

Behaves like a bucket rooted at a local directory, so the whole upload
pipeline can be exercised without MinIO or credentials.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from ..exceptions import StorageError


def _validate_key(key: str) -> PurePosixPath:
    pure = PurePosixPath(key)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise StorageError(f"Invalid object key: {key!r}")
    return pure


class LocalObjectStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root.joinpath(*_validate_key(key).parts)

    def put_fileobj(self, key: str, fileobj: BinaryIO) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as dest:
            shutil.copyfileobj(fileobj, dest)

    def get_file(self, key: str, dest: Path) -> None:
        source = self._path(key)
        if not source.is_file():
            raise StorageError(f"Object not found: {key!r}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)

    def iter_keys(self, prefix: str) -> Iterator[str]:
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                key = path.relative_to(self.root).as_posix()
                if key.startswith(prefix):
                    yield key

    def delete_prefix(self, prefix: str) -> int:
        keys = list(self.iter_keys(prefix))
        for key in keys:
            path = self._path(key)
            path.unlink(missing_ok=True)
            # prune now-empty directories up to the root
            parent = path.parent
            while parent != self.root and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        return len(keys)
