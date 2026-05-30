from __future__ import annotations
"""Benchmark business logic."""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundException
from app.domains.benchmarks.repository import BenchmarkRepository
from app.domains.benchmarks.schemas import BenchmarkCreate, BenchmarkUpdate


class BenchmarkService:
    def __init__(self, db: AsyncSession):
        self.repo = BenchmarkRepository(db)

    async def list_benchmarks(self, page: int = 1, page_size: int = 20):
        return await self.repo.list(page, page_size)

    async def get_benchmark(self, benchmark_id: uuid.UUID):
        benchmark = await self.repo.get_by_id(benchmark_id)
        if not benchmark:
            raise NotFoundException(f"Benchmark {benchmark_id} not found")
        return benchmark

    async def create_benchmark(self, data: BenchmarkCreate):
        return await self.repo.create(data.model_dump())

    async def update_benchmark(self, benchmark_id: uuid.UUID, data: BenchmarkUpdate):
        benchmark = await self.get_benchmark(benchmark_id)
        return await self.repo.update(benchmark, data.model_dump(exclude_unset=True))

    async def delete_benchmark(self, benchmark_id: uuid.UUID):
        benchmark = await self.get_benchmark(benchmark_id)
        await self.repo.delete(benchmark)
