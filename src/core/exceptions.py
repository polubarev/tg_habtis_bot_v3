from typing import Optional


class BotException(Exception):
    """Base exception for all bot errors."""

    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(message)
        self.user_message = user_message or "An error occurred. Please try again."


class ConfigurationError(BotException):
    """Raised when user configuration is invalid or missing."""


class SheetNotConfiguredError(ConfigurationError):
    """Raised when Google Sheet is not configured."""

    def __init__(self):
        super().__init__(
            "Google Sheet not configured",
            user_message="Please configure your Google Sheet first using /config.",
        )


class SheetValidationError(BotException):
    """Raised when sheet structure is invalid."""


class SheetAccessError(BotException):
    """Raised when Google Sheet is not accessible or writable."""


class SheetWriteError(BotException):
    """Raised when Google Sheet write fails for non-permission reasons."""


class ExternalTimeoutError(BotException):
    """Raised when an external service times out."""


class ExternalResponseError(BotException):
    """Raised when an external service returns an invalid response."""


class TranscriptionError(BotException):
    """Raised when audio transcription fails."""


class LLMError(BotException):
    """Raised when LLM request fails."""


class ExtractionError(LLMError):
    """Raised when structured extraction fails."""


class SessionExpiredError(BotException):
    """Raised when conversation session has expired."""

    def __init__(self):
        super().__init__(
            "Session expired",
            user_message="Session expired. Please start again.",
        )


class RateLimitError(BotException):
    """Raised when rate limit is exceeded."""

    def __init__(self):
        super().__init__(
            "Rate limit exceeded",
            user_message="Too many requests. Please wait a moment.",
        )


class ValidationError(BotException):
    """Raised when input validation fails."""
