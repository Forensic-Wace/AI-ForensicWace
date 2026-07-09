"""Schema descriptor registry and matching.

Descriptors live under ``FW_SCHEMAS_DIR`` as one folder per schema generation:

    schemas/whatsapp/<platform>/<descriptor-id>/
        descriptor.yaml     # detection rules, query file map, capabilities
        chat_list.sql       # parameterized queries (referenced by the yaml)
        ...

Adding support for a new WhatsApp version means adding such a folder plus a
synthetic fixture — no service code changes.
"""

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import get_settings
from ..exceptions import ConfigurationError, UnknownSchemaError, UnsupportedCapabilityError
from .fingerprint import Fingerprint, fingerprint_database

logger = logging.getLogger(__name__)


@dataclass
class SchemaDescriptor:
    id: str
    platform: str
    display_name: str
    priority: int
    required_tables: dict[str, list[str]]  # table -> required columns
    optional_tables: dict[str, list[str]] = field(default_factory=dict)
    queries: dict[str, str] = field(default_factory=dict)  # query name -> sql file
    capabilities: dict[str, bool] = field(default_factory=dict)
    base_dir: Path = Path(".")

    def matches(self, fingerprint: Fingerprint) -> bool:
        return all(fingerprint.has_table(t, cols) for t, cols in self.required_tables.items())

    def missing_optional(self, fingerprint: Fingerprint) -> list[str]:
        return [t for t, cols in self.optional_tables.items() if not fingerprint.has_table(t, cols)]


@dataclass
class SchemaMatch:
    descriptor: SchemaDescriptor
    missing_optional: list[str] = field(default_factory=list)
    _sql_cache: dict[str, str] = field(default_factory=dict, repr=False)

    def supports(self, query_name: str) -> bool:
        return self.descriptor.queries.get(query_name) is not None

    def sql(self, query_name: str) -> str:
        """The SQL text of a named query in this pack."""
        if not self.supports(query_name):
            raise UnsupportedCapabilityError(query_name, self.descriptor.id)
        if query_name not in self._sql_cache:
            sql_file = self.descriptor.base_dir / self.descriptor.queries[query_name]
            self._sql_cache[query_name] = sql_file.read_text(encoding="utf-8")
        return self._sql_cache[query_name]

    def summary(self) -> dict:
        return {
            "id": self.descriptor.id,
            "platform": self.descriptor.platform,
            "display_name": self.descriptor.display_name,
            "capabilities": {name: self.supports(name) for name in self.descriptor.queries},
            "missing_optional_tables": self.missing_optional,
        }


def _load_descriptor(descriptor_file: Path) -> SchemaDescriptor:
    data = yaml.safe_load(descriptor_file.read_text(encoding="utf-8"))
    detect = data.get("detect", {})
    return SchemaDescriptor(
        id=data["id"],
        platform=data["platform"],
        display_name=data.get("display_name", data["id"]),
        priority=int(data.get("priority", 0)),
        required_tables={t: list(cols or []) for t, cols in detect.get("required_tables", {}).items()},
        optional_tables={t: list(cols or []) for t, cols in detect.get("optional_tables", {}).items()},
        queries=data.get("queries", {}),
        capabilities=data.get("capabilities", {}),
        base_dir=descriptor_file.parent,
    )


@lru_cache
def _load_registry(schemas_dir: str) -> tuple[SchemaDescriptor, ...]:
    root = Path(schemas_dir)
    if not root.is_dir():
        raise ConfigurationError(
            f"WhatsApp schema registry not found at {root} — set FW_SCHEMAS_DIR "
            "to the schemas/whatsapp directory of the repository"
        )
    descriptors = [
        _load_descriptor(descriptor_file)
        for descriptor_file in sorted(root.glob("*/*/descriptor.yaml"))
    ]
    if not descriptors:
        raise ConfigurationError(f"No schema descriptors found under {root}")
    logger.info("Loaded %d WhatsApp schema descriptors from %s", len(descriptors), root)
    return tuple(sorted(descriptors, key=lambda d: d.priority, reverse=True))


def list_descriptors() -> list[SchemaDescriptor]:
    return list(_load_registry(str(get_settings().schemas_dir)))


def match_fingerprint(fingerprint: Fingerprint, platform: str) -> SchemaMatch:
    for descriptor in _load_registry(str(get_settings().schemas_dir)):
        if descriptor.platform == platform and descriptor.matches(fingerprint):
            match = SchemaMatch(descriptor, descriptor.missing_optional(fingerprint))
            if match.missing_optional:
                logger.warning(
                    "Schema %s matched with degraded support — missing optional tables: %s",
                    descriptor.id,
                    ", ".join(match.missing_optional),
                )
            return match
    raise UnknownSchemaError(platform, fingerprint.user_version, fingerprint.inventory())


@lru_cache(maxsize=256)
def _resolve_cached(db_path: str, platform: str, mtime_ns: int, size: int) -> SchemaMatch:
    return match_fingerprint(fingerprint_database(db_path), platform)


def resolve(db_path: Path | str, platform: str) -> SchemaMatch:
    """Fingerprint an evidence database and select its query pack (cached)."""
    stat = Path(db_path).stat()
    return _resolve_cached(str(db_path), platform, stat.st_mtime_ns, stat.st_size)


def clear_registry_cache() -> None:
    """Reset caches (used by tests that switch schemas dir or rebuild fixtures)."""
    _load_registry.cache_clear()
    _resolve_cached.cache_clear()
