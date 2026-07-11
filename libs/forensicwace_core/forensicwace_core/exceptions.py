"""Domain exceptions. Services translate these into transport-level errors."""


class ForensicWaceError(Exception):
    """Base class for all domain errors."""


class BackupNotFoundError(ForensicWaceError):
    """The requested backup id does not exist under the extraction root."""


class InvalidIdentifierError(ForensicWaceError):
    """A user-supplied identifier contains path separators or traversal."""


class ExtractionError(ForensicWaceError):
    """A WhatsApp evidence database could not be opened or queried."""


class ConfigurationError(ForensicWaceError):
    """A required setting is missing for the requested operation."""


class InvalidArchiveError(ForensicWaceError):
    """An uploaded backup archive is malformed, unsafe or not a backup."""


class StorageError(ForensicWaceError):
    """The object storage backend failed or is unreachable."""


class UnknownSchemaError(ForensicWaceError):
    """No schema descriptor matches the evidence database.

    Carries the fingerprint inventory so the error can be turned into an
    actionable report (and into a schema-support issue).
    """

    def __init__(self, platform: str, user_version: int, tables: dict[str, list[str]]):
        self.platform = platform
        self.user_version = user_version
        self.tables = tables
        super().__init__(
            f"No known {platform} WhatsApp schema matches this database "
            f"(user_version={user_version}, {len(tables)} tables/views found)"
        )


class UnsupportedCapabilityError(ForensicWaceError):
    """The matched schema descriptor does not provide the requested query."""

    def __init__(self, capability: str, descriptor_id: str):
        self.capability = capability
        self.descriptor_id = descriptor_id
        super().__init__(f"Schema {descriptor_id!r} does not support {capability!r}")
