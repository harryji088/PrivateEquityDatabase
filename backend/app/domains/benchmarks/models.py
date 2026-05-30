from __future__ import annotations
"""Benchmark index ORM models."""

from typing import Optional

import uuid
from datetime import date, datetime
from sqlalchemy import BigInteger, String, Date, Numeric, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    data: Mapped[list["BenchmarkData"]] = relationship(
        "BenchmarkData", back_populates="benchmark", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Benchmark {self.name}>"


class BenchmarkData(Base):
    __tablename__ = "benchmark_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False)
    daily_return: Mapped[Optional[float]] = mapped_column(Numeric(12, 8))

    # Relationships
    benchmark: Mapped["Benchmark"] = relationship("Benchmark", back_populates="data")

    __table_args__ = (
        UniqueConstraint("benchmark_id", "date", name="uq_benchmark_date"),
    )
