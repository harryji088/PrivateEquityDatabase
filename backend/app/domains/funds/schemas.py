from __future__ import annotations
"""Fund Pydantic schemas."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class FundBase(BaseModel):
    company_id: UUID = Field(..., description="所属公司ID")
    manager_id: Optional[UUID] = Field(None, description="基金经理ID")
    name: str = Field(..., min_length=1, max_length=255, description="基金名称")
    code: Optional[str] = Field(None, max_length=100, description="基金代码")
    strategy_type: str = Field(..., description="策略类型")
    inception_date: date = Field(..., description="成立日期")
    status: str = Field("active")
    aum: Optional[float] = Field(None, ge=0, description="基金规模(万元)")
    management_fee_rate: Optional[float] = Field(None, ge=0, le=1, description="管理费率")
    performance_fee_rate: Optional[float] = Field(None, ge=0, le=1, description="业绩报酬率")
    performance_fee_benchmark: Optional[str] = Field(None, max_length=50)
    hurdle_rate: Optional[float] = Field(None, ge=0, le=1)
    lockup_period_months: int = Field(0, ge=0)
    subscription_frequency: Optional[str] = Field(None, max_length=20)
    redemption_frequency: Optional[str] = Field(None, max_length=20)
    min_subscription_amount: Optional[float] = Field(None, ge=0)
    benchmark_id: Optional[UUID] = None
    description: Optional[str] = None


class FundCreate(FundBase):
    pass


class FundUpdate(BaseModel):
    company_id: Optional[UUID] = None
    manager_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=100)
    strategy_type: Optional[str] = None
    inception_date: Optional[date] = None
    status: Optional[str] = None
    aum: Optional[float] = Field(None, ge=0)
    management_fee_rate: Optional[float] = Field(None, ge=0, le=1)
    performance_fee_rate: Optional[float] = Field(None, ge=0, le=1)
    performance_fee_benchmark: Optional[str] = Field(None, max_length=50)
    hurdle_rate: Optional[float] = Field(None, ge=0, le=1)
    lockup_period_months: Optional[int] = Field(None, ge=0)
    subscription_frequency: Optional[str] = Field(None, max_length=20)
    redemption_frequency: Optional[str] = Field(None, max_length=20)
    min_subscription_amount: Optional[float] = Field(None, ge=0)
    benchmark_id: Optional[UUID] = None
    description: Optional[str] = None


class FundResponse(FundBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    company_name: Optional[str] = None
    manager_name: Optional[str] = None

    model_config = {"from_attributes": True}
