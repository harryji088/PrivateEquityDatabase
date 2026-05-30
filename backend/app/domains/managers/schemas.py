from __future__ import annotations
"""Fund manager Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ManagerBase(BaseModel):
    company_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=100, description="姓名")
    title: Optional[str] = Field(None, max_length=100, description="职务")
    experience_years: Optional[float] = Field(None, ge=0, description="从业年限")
    education: Optional[str] = Field(None, max_length=255, description="学历")
    certifications: Optional[str] = Field(None, description="资质证书")
    bio: Optional[str] = Field(None, description="个人简介")
    photo_url: Optional[str] = Field(None, max_length=500)


class ManagerCreate(ManagerBase):
    pass


class ManagerUpdate(BaseModel):
    company_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    title: Optional[str] = Field(None, max_length=100)
    experience_years: Optional[float] = Field(None, ge=0)
    education: Optional[str] = Field(None, max_length=255)
    certifications: Optional[str] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)


class ManagerResponse(ManagerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
