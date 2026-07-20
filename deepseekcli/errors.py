from __future__ import annotations

from typing import Any


class DeepSeekError(Exception):
    """Base exception for the deepseek client library."""


class NetworkError(DeepSeekError):
    """Raised for network-related errors (requests timeouts, connection errors)."""


class APIError(DeepSeekError):
    """Raised when the remote API returns an error status or unexpected HTTP code.

    Attributes:
        status_code: optional HTTP status code
        body: optional response body (truncated)
    """

    def __init__(self, message: str, status_code: int | None = None, body: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class InvalidResponseError(DeepSeekError):
    """Raised when an API response is malformed or missing expected fields."""


class PoWSolverError(DeepSeekError):
    """Base for PoW related errors."""


class PoWLoadError(PoWSolverError):
    """Raised when the PoW WASM module cannot be loaded or executed."""


class PoWChallengeError(PoWSolverError):
    """Raised when the PoW challenge payload is invalid or incomplete."""


class StorageError(DeepSeekError):
    """Raised for local storage/read/write failures."""


class AuthError(StorageError):
    """Raised for credential-related storage errors."""
