from __future__ import annotations
"""Fund company Pydantic schemas."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="公司名称")
    short_name: Optional[str] = Field(None, max_length=100)
    registration_code: Optional[str] = Field(None, max_length=100, description="备案编号")
    registration_date: Optional[date] = None
    total_aum: Optional[float] = Field(None, ge=0, description="管理总规模(亿元)")
    founding_date: Optional[date] = None
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    contact_info: Optional[str] = None
    description: Optional[str] = None
    status: str = Field("active", pattern="^(active|inactive|deregistered)$")


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    short_name: Optional[str] = Field(None, max_length=100)
    registration_code: Optional[str] = Field(None, max_length=100)
    registration_date: Optional[date] = None
    total_aum: Optional[float] = Field(None, ge=0)
    founding_date: Optional[date] = None
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    contact_info: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive|deregistered)$")


class CompanyResponse(CompanyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyListParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    status: Optional[str] = None
    search: Optional[str] = Field(None, description="Search by name")
