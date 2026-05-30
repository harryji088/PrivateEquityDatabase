from __future__ import annotations
"""Fund company ORM model."""

from typing import Optional

import uuid
from datetime import date, datetime
from sqlalchemy import String, Date, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class FundCompany(Base):
    __tablename__ = "fund_companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(100))
    registration_code: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    registration_date: Mapped[Optional[date]] = mapped_column(Date)
    total_aum: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    founding_date: Mapped[Optional[date]] = mapped_column(Date)
    province: Mapped[Optional[str]] = mapped_column(String(50))
    city: Mapped[Optional[str]] = mapped_column(String(50))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    contact_info: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    managers: Mapped[list["FundManager"]] = relationship(
        "FundManager", back_populates="company", cascade="all, delete-orphan"
    )
    funds: Mapped[list["Fund"]] = relationship(
        "Fund", back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FundCompany {self.name}>"
