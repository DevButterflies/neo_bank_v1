"""Typed exceptions shared by every bank service."""


class BankError(Exception):
    """Base error surfaced to HTTP clients as a JSON detail."""

    status_code = 500
    detail = "Internal error"

    def __init__(self, detail: str | None = None, status_code: int | None = None) -> None:
        super().__init__(detail or self.detail)
        self.detail = detail or self.detail
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(BankError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(BankError):
    status_code = 409
    detail = "Resource conflict"


class ValidationError(BankError):
    status_code = 422
    detail = "Request validation failed"