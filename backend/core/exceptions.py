"""Typed application errors.

Every error raised in the application is an :class:`AppError` subclass that
carries an HTTP status plus a machine-readable ``code`` and renders as the
single, consistent JSON envelope required by the API contract::

    {"error": {"code": "not_found", "message": "..."}}

The FastAPI exception handlers in ``backend.main`` convert these into HTTP
responses (see ``main._register_exception_handlers``).
"""
from __future__ import annotations


class AppError(Exception):
    """Base error: HTTP status + machine-readable code + human message."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


class NotFoundError(AppError):
    """Raised for unknown resources (404)."""

    status_code = 404
    code = "not_found"

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message)


class InvalidInputError(AppError):
    """Raised for malformed / rejected client input (400)."""

    status_code = 400
    code = "invalid_input"


class ConflictError(AppError):
    """Raised when the request conflicts with current state (409)."""

    status_code = 409
    code = "conflict"


class JobBusyError(ConflictError):
    """Raised when an action requires a finished job but it is still running."""

    code = "job_running"

    def __init__(self, message: str = "Job is still running") -> None:
        super().__init__(message)


class ServiceUnavailableError(AppError):
    """Raised when a dependency (DB, scraper engine, exporters) is unavailable."""

    status_code = 503
    code = "service_unavailable"