from __future__ import annotations
"""Benchmark data access layer."""

import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.benchmarks.models import Benchmark, BenchmarkData


class BenchmarkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, page: int = 1, page_size: int = 20) -> tuple[list[Benchmark], int]:
        query = select(Benchmark)
        total = (await self.db.execute(select(func.count(Benchmark.id)))).scalar() or 0
        query = query.order_by(Benchmark.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(self, benchmark_id: uuid.UUID) -> Optional[Benchmark]:
        result = await self.db.execute(
            select(Benchmark).where(Benchmark.id == benchmark_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Benchmark:
        benchmark = Benchmark(**data)
        self.db.add(benchmark)
        await self.db.flush()
        return benchmark

    async def update(self, benchmark: Benchmark, data: dict) -> Benchmark:
        for key, value in data.items():
            if value is not None:
                setattr(benchmark, key, value)
        await self.db.flush()
        return benchmark

    async def delete(self, benchmark: Benchmark) -> None:
        await self.db.delete(benchmark)
        await self.db.flush()
