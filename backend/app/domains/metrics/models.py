from __future__ import annotations
"""Performance metrics cache ORM model."""

from typing import Optional

import uuid
from datetime import date, datetime
from sqlalchemy import String, Date, Numeric, Text, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funds.id", ondelete="CASCADE"), nullable=False
    )
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Return metrics
    cumulative_return: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    annualized_return: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    monthly_returns: Mapped[Optional[dict]] = mapped_column(JSONB)
    best_month_return: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    worst_month_return: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))

    # Risk metrics
    annualized_volatility: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    max_drawdown: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    max_drawdown_start_date: Mapped[Optional[date]] = mapped_column(Date)
    max_drawdown_end_date: Mapped[Optional[date]] = mapped_column(Date)
    max_drawdown_recovery_date: Mapped[Optional[date]] = mapped_column(Date)
    downside_deviation: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    var_95: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    var_99: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    cvar_95: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))

    # Risk-adjusted return metrics
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    sortino_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    calmar_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    information_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    treynor_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))

    # Other statistics
    win_rate: Mapped[Optional[float]] = mapped_column(Numeric(8, 6))
    profit_loss_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    alpha: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    beta: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    correlation: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    tracking_error: Mapped[Optional[float]] = mapped_column(Numeric(15, 8))
    skewness: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    kurtosis: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    positive_days: Mapped[Optional[int]] = mapped_column(Integer)
    negative_days: Mapped[Optional[int]] = mapped_column(Integer)
    total_days: Mapped[Optional[int]] = mapped_column(Integer)

    # Rolling metrics
    rolling_metrics: Mapped[Optional[dict]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    fund: Mapped["Fund"] = relationship("Fund", back_populates="metrics")

    __table_args__ = (
        UniqueConstraint(
            "fund_id", "period_type", "calculation_date",
            name="uq_fund_period_date"
        ),
    )

    def __repr__(self) -> str:
        return f"<PerformanceMetric fund={self.fund_id} period={self.period_type}>"
