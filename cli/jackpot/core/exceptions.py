"""
jackpot.core.exceptions
~~~~~~~~~~~~~~~~~~~~~~~
All exceptions raised by the JACKPOT SDK and CLI.
"""


class JACKPOTError(Exception):
    """Base exception for all JACKPOT errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AuthError(JACKPOTError):
    """Authentication or authorisation failed (401, 403)."""


class NotFoundError(JACKPOTError):
    """Requested resource does not exist (404)."""


class ValidationError(JACKPOTError):
    """Metadata failed tier-aware validation (422)."""

    def __init__(
        self,
        message: str,
        errors: list[str] | None = None,
        tier2_missing: list[str] | None = None,
        tier3_missing: list[str] | None = None,
    ):
        super().__init__(message, status_code=422)
        self.errors = errors or []
        self.tier2_missing = tier2_missing or []
        self.tier3_missing = tier3_missing or []


class ConflictError(JACKPOTError):
    """Duplicate resource or conflicting state (409)."""


class ScrubPendingError(JACKPOTError):
    """Files not yet available — scrub in progress or awaiting approval (409)."""


class ServerError(JACKPOTError):
    """Unexpected server error (500)."""


class ConfigError(JACKPOTError):
    """Missing or invalid local configuration (~/.jackpot/config.toml)."""


class TokenExpiredError(AuthError):
    """API token has expired. Run `jackpot auth login` to refresh."""
