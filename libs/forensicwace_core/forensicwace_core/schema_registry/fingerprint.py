"""Schema fingerprinting of WhatsApp evidence databases.

The fingerprint is the full structural inventory of the SQLite file:
``PRAGMA user_version`` plus every table/view with its columns. It is matched
against the schema descriptors to select the right query pack, and it is what
an unknown-schema report shows (structure only — never row data).
"""

from dataclasses import dataclass, field
from pathlib import Path

from ..whatsapp.sqlite import open_readonly


@dataclass
class Fingerprint:
    user_version: int
    tables: dict[str, set[str]] = field(default_factory=dict)  # name -> columns (views included)

    def has_table(self, name: str, required_columns: list[str] | None = None) -> bool:
        columns = self.tables.get(name)
        if columns is None:
            return False
        return all(col in columns for col in required_columns or [])

    def inventory(self) -> dict[str, list[str]]:
        """JSON-friendly structure listing, sorted for stable output."""
        return {name: sorted(cols) for name, cols in sorted(self.tables.items())}


def fingerprint_database(db_path: Path | str) -> Fingerprint:
    conn = open_readonly(db_path)
    try:
        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
        names = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'"
            )
        ]
        tables = {
            name: {row["name"] for row in conn.execute(f"PRAGMA table_info({name!r})")}
            for name in names
        }
        return Fingerprint(user_version=user_version, tables=tables)
    finally:
        conn.close()
