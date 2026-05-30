from __future__ import annotations
"""Fund manager ORM model."""

from typing import Optional

import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class FundManager(Base):
    __tablename__ = "fund_managers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fund_companies.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(100))
    experience_years: Mapped[Optional[float]] = mapped_column(Numeric(4, 1))
    education: Mapped[Optional[str]] = mapped_column(String(255))
    certifications: Mapped[Optional[str]] = mapped_column(Text)
    bio: Mapped[Optional[str]] = mapped_column(Text)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company: Mapped["Optional[FundCompany]"] = relationship(
        "FundCompany", back_populates="managers"
    )
    funds: Mapped[list["Fund"]] = relationship("Fund", back_populates="manager")

    def __repr__(self) -> str:
        return f"<FundManager {self.name}>"
