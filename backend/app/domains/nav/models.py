from __future__ import annotations
"""NAV data ORM model — the core time-series data table."""

from typing import Optional

import uuid
from datetime import date, datetime
from sqlalchemy import BigInteger, String, Date, Numeric, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class NavData(Base):
    __tablename__ = "nav_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funds.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    cumulative_nav: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    daily_return: Mapped[Optional[float]] = mapped_column(Numeric(12, 8))
    adjusted_nav: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    dividend_amount: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    fund: Mapped["Fund"] = relationship("Fund", back_populates="nav_data")

    __table_args__ = (
        UniqueConstraint("fund_id", "date", name="uq_fund_date"),
    )

    def __repr__(self) -> str:
        return f"<NavData fund={self.fund_id} date={self.date} nav={self.nav}>"
