"""Public error hierarchy used across the application."""

from __future__ import annotations


class AgentError(Exception):
    """Base class for expected application failures."""


class ValidationError(AgentError):
    def __init__(self, message: str, *, errors: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or {}


class CliError(AgentError):
    category = "cli_error"

    def __init__(self, message: str, *, exit_code: int | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class CliNotFoundError(CliError):
    category = "cli_not_found"


class CliTimeoutError(CliError):
    category = "cli_timeout"


class CliProcessError(CliError):
    category = "cli_process_failed"


class CliOutputParseError(CliError):
    category = "cli_output_parse_failed"


class ChatServiceError(CliError):
    category = "chat_service_failed"


class PersistenceError(AgentError):
    pass
