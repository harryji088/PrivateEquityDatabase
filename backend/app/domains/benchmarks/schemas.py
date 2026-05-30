from __future__ import annotations
"""Benchmark Pydantic schemas."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class BenchmarkBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class BenchmarkCreate(BenchmarkBase):
    pass


class BenchmarkUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class BenchmarkResponse(BenchmarkBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class BenchmarkDataBase(BaseModel):
    benchmark_id: UUID
    date: date
    value: float = Field(..., gt=0)


class BenchmarkDataCreate(BenchmarkDataBase):
    pass


class BenchmarkDataResponse(BenchmarkDataBase):
    id: int
    daily_return: Optional[float] = None

    model_config = {"from_attributes": True}
