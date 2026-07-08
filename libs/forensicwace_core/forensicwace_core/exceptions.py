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
