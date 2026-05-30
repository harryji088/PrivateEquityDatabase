"""Global exception handlers and custom exceptions."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class NotFoundException(Exception):
    """Raised when a requested resource is not found."""
    def __init__(self, message: str = "Resource not found"):
        self.message = message


class ValidationException(Exception):
    """Raised when input validation fails."""
    def __init__(self, message: str = "Validation error"):
        self.message = message


class ConflictException(Exception):
    """Raised when a data conflict occurs (e.g., duplicate)."""
    def __init__(self, message: str = "Resource already exists"):
        self.message = message


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(NotFoundException)
    async def not_found_handler(request: Request, exc: NotFoundException):
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @app.exception_handler(ValidationException)
    async def validation_handler(request: Request, exc: ValidationException):
        return JSONResponse(status_code=422, content={"detail": exc.message})

    @app.exception_handler(ConflictException)
    async def conflict_handler(request: Request, exc: ConflictException):
        return JSONResponse(status_code=409, content={"detail": exc.message})

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})
