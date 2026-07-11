"""Uploaded backup archives: validation, object-storage mirroring, hydration.

Uploads arrive as ZIP archives of an extraction folder (Android: msgstore.db
plus optional Media/; iOS: the iTunes-style backup directory). Members are
never extracted with ``extractall``: every name is validated first (zip-slip,
absolute paths, drive letters) and streamed to its destination explicitly.
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..constants import IOS_MANIFEST_DB, IOS_MANIFEST_PLIST
from ..exceptions import InvalidArchiveError
from ..storage.base import ObjectStorage


def object_prefix(project_id: str, platform: str, identifier: str) -> str:
    """Bucket layout shared by upload, hydration and deletion."""
    return f"projects/{project_id}/{platform}/{identifier}/"


@dataclass
class ArchiveInventory:
    root_prefix: str  # common wrapping folder stripped from every member ("" when flat)
    file_count: int
    total_bytes: int  # uncompressed


def _member_relpath(name: str) -> PurePosixPath | None:
    """Normalized safe relative path of a member; None for directory entries."""
    normalized = name.replace("\\", "/")
    if normalized.endswith("/") or not normalized:
        return None
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or any(":" in part for part in pure.parts):
        raise InvalidArchiveError(f"Archive member has an unsafe path: {name!r}")
    return pure


def _strip_common_root(paths: list[PurePosixPath]) -> tuple[str, list[PurePosixPath]]:
    """Peel wrapping folders while every member sits under the same one, so
    'zip of the folder' and 'zip of its contents' are equivalent."""
    prefix_parts: list[str] = []
    while all(len(p.parts) >= 2 for p in paths):
        roots = {p.parts[0] for p in paths}
        if len(roots) != 1:
            break
        prefix_parts.append(roots.pop())
        paths = [PurePosixPath(*p.parts[1:]) for p in paths]
    return "/".join(prefix_parts), paths


def _safe_entries(archive: zipfile.ZipFile) -> tuple[str, list[tuple[zipfile.ZipInfo, PurePosixPath]]]:
    """(root prefix, [(member, stripped safe path)]) for all file members."""
    entries = []
    for info in archive.infolist():
        relpath = _member_relpath(info.filename)
        if relpath is not None:
            entries.append((info, relpath))
    if not entries:
        raise InvalidArchiveError("Archive contains no files")
    root_prefix, stripped = _strip_common_root([path for _, path in entries])
    return root_prefix, [(info, path) for (info, _), path in zip(entries, stripped)]


def _check_platform_markers(platform: str, paths: list[PurePosixPath]) -> None:
    top_level = {p.parts[0] for p in paths if len(p.parts) == 1}
    if platform == "ios":
        missing = {IOS_MANIFEST_DB, IOS_MANIFEST_PLIST} - top_level
        if missing:
            raise InvalidArchiveError(
                f"Not an iOS device backup: missing {', '.join(sorted(missing))} at the archive root"
            )
    else:
        if not any(name.endswith(".db") for name in top_level):
            raise InvalidArchiveError(
                "Not an Android extraction: no .db database (e.g. msgstore.db) at the archive root"
            )


def inspect_archive(zip_path: Path, platform: str) -> ArchiveInventory:
    """Validate structure and safety of an uploaded archive without extracting."""
    if not zipfile.is_zipfile(zip_path):
        raise InvalidArchiveError("Upload is not a ZIP archive")
    with zipfile.ZipFile(zip_path) as archive:
        root_prefix, entries = _safe_entries(archive)
        _check_platform_markers(platform, [path for _, path in entries])
        return ArchiveInventory(
            root_prefix=root_prefix,
            file_count=len(entries),
            total_bytes=sum(info.file_size for info, _ in entries),
        )


def mirror_to_storage(storage: ObjectStorage, prefix: str, zip_path: Path) -> ArchiveInventory:
    """Stream every archive member to object storage under ``prefix``."""
    with zipfile.ZipFile(zip_path) as archive:
        root_prefix, entries = _safe_entries(archive)
        inventory = ArchiveInventory(root_prefix=root_prefix, file_count=0, total_bytes=0)
        for info, relpath in entries:
            with archive.open(info) as member:
                storage.put_fileobj(prefix + relpath.as_posix(), member)
            inventory.file_count += 1
            inventory.total_bytes += info.file_size
    return inventory


def extract_to_dir(zip_path: Path, dest_dir: Path) -> int:
    """Safely extract the archive (common root stripped) into ``dest_dir``."""
    import shutil

    count = 0
    with zipfile.ZipFile(zip_path) as archive:
        for info, relpath in _safe_entries(archive)[1]:
            target = dest_dir.joinpath(*relpath.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as member, target.open("wb") as out:
                shutil.copyfileobj(member, out)
            count += 1
    return count


def hydrate_from_storage(storage: ObjectStorage, prefix: str, dest_dir: Path) -> int:
    """Download every object under ``prefix`` into ``dest_dir``."""
    count = 0
    for key in storage.iter_keys(prefix):
        relative = PurePosixPath(key[len(prefix) :])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise InvalidArchiveError(f"Refusing to hydrate unsafe object key: {key!r}")
        storage.get_file(key, dest_dir.joinpath(*relative.parts))
        count += 1
    if count == 0:
        raise InvalidArchiveError(f"No objects found under {prefix!r}")
    return count
