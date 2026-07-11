"""Uploaded-archive handling: validation, storage mirroring, hydration."""

import io
import plistlib
import zipfile
from pathlib import Path

import pytest

from forensicwace_core.backups import packaging
from forensicwace_core.exceptions import InvalidArchiveError, StorageError
from forensicwace_core.storage.local import LocalObjectStorage


def make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return path


def android_members(prefix: str = "") -> dict[str, bytes]:
    return {
        f"{prefix}msgstore.db": b"sqlite-bytes",
        f"{prefix}Media/WhatsApp Images/IMG-1.jpg": b"jpeg-bytes",
    }


def ios_members(prefix: str = "") -> dict[str, bytes]:
    return {
        f"{prefix}Manifest.db": b"manifest-db",
        f"{prefix}Manifest.plist": plistlib.dumps({"Lockdown": {"DeviceName": "test"}}),
        f"{prefix}7c/7c7fba66680ef796b916b067077cc246adacf01d": b"chatstorage",
    }


# --- inspect_archive --------------------------------------------------------


def test_inspect_valid_android_archive(tmp_path):
    archive = make_zip(tmp_path / "up.zip", android_members())
    inventory = packaging.inspect_archive(archive, "android")
    assert inventory.file_count == 2
    assert inventory.root_prefix == ""
    assert inventory.total_bytes == len(b"sqlite-bytes") + len(b"jpeg-bytes")


def test_inspect_strips_wrapping_folder(tmp_path):
    archive = make_zip(tmp_path / "up.zip", android_members("my extraction/"))
    inventory = packaging.inspect_archive(archive, "android")
    assert inventory.root_prefix == "my extraction"


def test_inspect_valid_ios_archive(tmp_path):
    archive = make_zip(tmp_path / "up.zip", ios_members("00008030-000A/"))
    assert packaging.inspect_archive(archive, "ios").file_count == 3


def test_android_archive_without_db_is_rejected(tmp_path):
    archive = make_zip(tmp_path / "up.zip", {"Media/IMG-1.jpg": b"x"})
    with pytest.raises(InvalidArchiveError, match="msgstore.db"):
        packaging.inspect_archive(archive, "android")


def test_ios_archive_without_manifests_is_rejected(tmp_path):
    archive = make_zip(tmp_path / "up.zip", {"Manifest.db": b"x", "7c/xx": b"y"})
    with pytest.raises(InvalidArchiveError, match="Manifest.plist"):
        packaging.inspect_archive(archive, "ios")


def test_non_zip_upload_is_rejected(tmp_path):
    junk = tmp_path / "up.zip"
    junk.write_bytes(b"PDF-1.4 not a zip")
    with pytest.raises(InvalidArchiveError, match="not a ZIP"):
        packaging.inspect_archive(junk, "android")


@pytest.mark.parametrize("evil", ["../evil.db", "/abs/evil.db", "C:/evil.db", "a/../../evil.db"])
def test_zip_slip_members_are_rejected(tmp_path, evil):
    archive = make_zip(tmp_path / "up.zip", {"msgstore.db": b"x", evil: b"y"})
    with pytest.raises(InvalidArchiveError, match="unsafe path"):
        packaging.inspect_archive(archive, "android")


def test_empty_archive_is_rejected(tmp_path):
    archive = make_zip(tmp_path / "up.zip", {})
    with pytest.raises(InvalidArchiveError, match="no files"):
        packaging.inspect_archive(archive, "android")


def test_single_flat_db_is_not_treated_as_root_folder(tmp_path):
    archive = make_zip(tmp_path / "up.zip", {"msgstore.db": b"x"})
    inventory = packaging.inspect_archive(archive, "android")
    assert inventory.root_prefix == ""
    assert inventory.file_count == 1


# --- storage mirroring / hydration ------------------------------------------


def test_mirror_extract_hydrate_roundtrip(tmp_path):
    storage = LocalObjectStorage(tmp_path / "bucket")
    archive = make_zip(tmp_path / "up.zip", android_members("case42/"))
    prefix = packaging.object_prefix("proj-1", "android", "case42")

    inventory = packaging.mirror_to_storage(storage, prefix, archive)
    assert inventory.file_count == 2
    assert sorted(storage.iter_keys(prefix)) == [
        "projects/proj-1/android/case42/Media/WhatsApp Images/IMG-1.jpg",
        "projects/proj-1/android/case42/msgstore.db",
    ]

    extracted = tmp_path / "extracted"
    assert packaging.extract_to_dir(archive, extracted) == 2
    assert (extracted / "msgstore.db").read_bytes() == b"sqlite-bytes"
    assert (extracted / "Media" / "WhatsApp Images" / "IMG-1.jpg").is_file()

    hydrated = tmp_path / "hydrated"
    assert packaging.hydrate_from_storage(storage, prefix, hydrated) == 2
    assert (hydrated / "msgstore.db").read_bytes() == b"sqlite-bytes"


def test_hydrate_missing_prefix_fails(tmp_path):
    storage = LocalObjectStorage(tmp_path / "bucket")
    with pytest.raises(InvalidArchiveError, match="No objects"):
        packaging.hydrate_from_storage(storage, "projects/nope/", tmp_path / "out")


def test_local_storage_delete_prefix(tmp_path):
    storage = LocalObjectStorage(tmp_path / "bucket")
    storage.put_fileobj("projects/p1/android/a/msgstore.db", io.BytesIO(b"x"))
    storage.put_fileobj("projects/p1/android/a/Media/i.jpg", io.BytesIO(b"y"))
    storage.put_fileobj("projects/p2/ios/b/Manifest.db", io.BytesIO(b"z"))

    assert storage.delete_prefix("projects/p1/") == 2
    assert list(storage.iter_keys("projects/")) == ["projects/p2/ios/b/Manifest.db"]


def test_local_storage_rejects_traversal_keys(tmp_path):
    storage = LocalObjectStorage(tmp_path / "bucket")
    with pytest.raises(StorageError):
        storage.put_fileobj("../outside", io.BytesIO(b"x"))
