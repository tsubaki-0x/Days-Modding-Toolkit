class ToolkitError(Exception):
    """Base exception for expected toolkit failures."""


class UnsupportedFormatError(ToolkitError):
    """Raised when a binary format has not been confirmed yet."""

