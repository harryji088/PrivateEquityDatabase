from __future__ import annotations
"""Fund (基金产品) ORM model."""

from typing import Optional

import uuid
from datetime import date, datetime
from sqlalchemy import String, Date, Numeric, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Fund(Base):
    __tablename__ = "funds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fund_companies.id", ondelete="RESTRICT"), nullable=False
    )
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fund_managers.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    inception_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    aum: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    management_fee_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    performance_fee_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    performance_fee_benchmark: Mapped[Optional[str]] = mapped_column(String(50))
    hurdle_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    lockup_period_months: Mapped[int] = mapped_column(Integer, default=0)
    subscription_frequency: Mapped[Optional[str]] = mapped_column(String(20))
    redemption_frequency: Mapped[Optional[str]] = mapped_column(String(20))
    min_subscription_amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    benchmark_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benchmarks.id", ondelete="SET NULL")
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company: Mapped["FundCompany"] = relationship("FundCompany", back_populates="funds")
    manager: Mapped["Optional[FundManager]"] = relationship("FundManager", back_populates="funds")
    nav_data: Mapped[list["NavData"]] = relationship(
        "NavData", back_populates="fund", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["PerformanceMetric"]] = relationship(
        "PerformanceMetric", back_populates="fund", cascade="all, delete-orphan"
    )
    benchmark: Mapped["Optional[Benchmark]"] = relationship("Benchmark", foreign_keys=[benchmark_id])

    def __repr__(self) -> str:
        return f"<Fund {self.name}>"
