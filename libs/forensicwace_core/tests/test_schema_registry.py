"""Compatibility matrix: every fixture must match its descriptor and every
query in the matched pack must execute against it."""

import re
import sqlite3
from pathlib import Path

import pytest

from forensicwace_core.exceptions import UnknownSchemaError, UnsupportedCapabilityError
from forensicwace_core.schema_registry import fingerprint_database, list_descriptors, resolve
from forensicwace_core.schema_registry.registry import match_fingerprint
from forensicwace_core.whatsapp.sqlite import query_dicts

REPO_ROOT = Path(__file__).parents[3]
FIXTURES_DIR = REPO_ROOT / "schemas" / "whatsapp" / "fixtures"

# fixture file stem -> descriptor id it must match
EXPECTED_MATCHES = {
    "android-modern-chatview": "android-modern-chatview",
    "ios-chatstorage-z": "ios-chatstorage-z",
}

# Bindings for every named parameter appearing in any pack query.
DEFAULT_PARAMS = {
    "jid_pattern": "%0000000001%",
    "phone_pattern": "%0000000001%",
    "group_pattern": "%",
}


def build_fixture(sql_file: Path, tmp_path: Path) -> Path:
    db_path = tmp_path / f"{sql_file.stem}.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(sql_file.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    return db_path


def named_params(sql: str) -> dict:
    return {name: DEFAULT_PARAMS[name] for name in set(re.findall(r":(\w+)", sql))}


def fixture_files() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.sql"))


def test_every_fixture_has_an_expectation_and_vice_versa():
    assert {f.stem for f in fixture_files()} == set(EXPECTED_MATCHES)


@pytest.mark.parametrize("sql_file", fixture_files(), ids=lambda p: p.stem)
def test_fixture_matches_expected_descriptor(sql_file, tmp_path):
    db_path = build_fixture(sql_file, tmp_path)
    descriptor_id = EXPECTED_MATCHES[sql_file.stem]
    platform = descriptor_id.split("-")[0]
    match = resolve(db_path, platform)
    assert match.descriptor.id == descriptor_id
    assert match.missing_optional == []


@pytest.mark.parametrize("sql_file", fixture_files(), ids=lambda p: p.stem)
def test_every_pack_query_runs_against_its_fixture(sql_file, tmp_path):
    """The support matrix: each named query executes and returns rows/columns."""
    db_path = build_fixture(sql_file, tmp_path)
    platform = EXPECTED_MATCHES[sql_file.stem].split("-")[0]
    match = resolve(db_path, platform)
    executed = 0
    for query_name in match.descriptor.queries:
        if not match.supports(query_name):
            continue
        sql = match.sql(query_name)
        query_dicts(db_path, sql, named_params(sql))  # must not raise
        executed += 1
    assert executed > 0


def test_unknown_schema_yields_actionable_report(tmp_path):
    db_path = tmp_path / "mystery.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE something_new (id INTEGER, payload TEXT)")
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()

    with pytest.raises(UnknownSchemaError) as excinfo:
        resolve(db_path, "android")
    error = excinfo.value
    assert error.platform == "android"
    assert error.user_version == 99
    assert error.tables == {"something_new": ["id", "payload"]}


def test_unsupported_capability_is_explicit(tmp_path):
    db_path = build_fixture(FIXTURES_DIR / "android-modern-chatview.sql", tmp_path)
    match = resolve(db_path, "android")
    assert not match.supports("blocked_contacts")
    with pytest.raises(UnsupportedCapabilityError):
        match.sql("blocked_contacts")


def test_fingerprint_inventory_is_structure_only(tmp_path):
    db_path = build_fixture(FIXTURES_DIR / "android-modern-chatview.sql", tmp_path)
    fp = fingerprint_database(db_path)
    inventory = str(fp.inventory())
    assert "hello from contact" not in inventory  # never row data


def test_registry_lists_all_descriptors():
    ids = {d.id for d in list_descriptors()}
    assert set(EXPECTED_MATCHES.values()) <= ids


def test_ios_extraction_values(tmp_path):
    """Sanity beyond 'executes': the iOS pack returns the fixture's data."""
    from forensicwace_core.whatsapp.sqlite import query_dicts as run

    db_path = build_fixture(FIXTURES_DIR / "ios-chatstorage-z.sql", tmp_path)
    match = match_fingerprint(fingerprint_database(db_path), "ios")

    chats = run(db_path, match.sql("chat_list"))
    assert chats and chats[0]["Contact"] == "Test Contact"

    counters = run(db_path, match.sql("private_chat_counters"), {"jid_pattern": "%0000000001%"})
    assert counters[0]["TotalMessages"] >= 2

    blocked = run(db_path, match.sql("blocked_contacts"))
    assert blocked[0]["PhoneNumber"].startswith("3900000000")

    gps = run(db_path, match.sql("gps_locations"))
    assert gps and gps[0]["Latitude"] == 41.1171
