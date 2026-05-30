from __future__ import annotations
"""Shared API schemas — pagination, error responses, etc."""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response envelope."""
    data: list[T]
    total: int
    page: int
    page_size: int

    class Config:
        from_attributes = True


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope."""
    data: Optional[T] = None
    message: str = "ok"
