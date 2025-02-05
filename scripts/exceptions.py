"""Custom exceptions for the project."""


class LyricItError(Exception):
    """Base exception for all project-specific errors."""

    pass


class URLCheckError(LyricItError):
    """Raised when there's an error checking or parsing URLs."""

    pass


class AppleMusicAPIError(LyricItError):
    """Raised when there's an error with Apple Music API operations."""

    pass


class DownloadError(LyricItError):
    """Raised when there's an error downloading content."""

    pass


class StreamInfoError(LyricItError):
    """Raised when there's an error getting stream information."""

    pass


class LegacyDownloadError(LyricItError):
    """Raised when there's an error in legacy download operations."""

    pass


class SongError(LyricItError):
    """Raised when there's an error processing song data."""

    pass
