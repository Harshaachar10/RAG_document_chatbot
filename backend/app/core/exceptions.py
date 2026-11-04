from __future__ import annotations

from typing import Any, Dict, Optional


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("NOT_FOUND", message, status_code=404, details=details)


class ConflictError(AppError):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(code, message, status_code=409, details=details)


class ValidationAppError(AppError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("VALIDATION_ERROR", message, status_code=422, details=details)


class DatasetValidationError(AppError):
    def __init__(self, errors: list) -> None:
        preview = errors[:40]
        super().__init__(
            "DATASET_INVALID",
            "The CSV dataset failed validation. No records were dropped.",
            status_code=500,
            details={"error_count": len(errors), "errors": preview},
        )
        self.errors = errors
