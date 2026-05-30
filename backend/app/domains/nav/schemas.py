from __future__ import annotations
"""NAV data Pydantic schemas."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class NavDataBase(BaseModel):
    fund_id: UUID
    date: date
    nav: float = Field(..., gt=0, description="单位净值")
    cumulative_nav: Optional[float] = Field(None, ge=0, description="累计净值")
    adjusted_nav: Optional[float] = Field(None, ge=0, description="复权净值")
    dividend_amount: float = Field(0, ge=0, description="分红金额")


class NavDataCreate(NavDataBase):
    pass


class NavDataBulkCreate(BaseModel):
    records: list[NavDataCreate] = Field(..., min_length=1, max_length=10000)


class NavDataUpdate(BaseModel):
    nav: Optional[float] = Field(None, gt=0)
    cumulative_nav: Optional[float] = Field(None, ge=0)
    daily_return: Optional[float] = None
    adjusted_nav: Optional[float] = Field(None, ge=0)
    dividend_amount: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


class NavDataResponse(NavDataBase):
    id: int
    daily_return: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NavDataQuery(BaseModel):
    fund_id: UUID
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(100, ge=1, le=500)
