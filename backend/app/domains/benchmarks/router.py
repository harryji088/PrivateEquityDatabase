from __future__ import annotations
"""Benchmark REST endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.domains.benchmarks.schemas import BenchmarkCreate, BenchmarkUpdate, BenchmarkResponse
from app.domains.benchmarks.service import BenchmarkService
from app.api.v1.schemas import PaginatedResponse

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> BenchmarkService:
    return BenchmarkService(db)


@router.get("", response_model=PaginatedResponse[BenchmarkResponse])
async def list_benchmarks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: BenchmarkService = Depends(get_service),
):
    items, total = await svc.list_benchmarks(page, page_size)
    return PaginatedResponse(data=items, total=total, page=page, page_size=page_size)


@router.get("/{benchmark_id}", response_model=BenchmarkResponse)
async def get_benchmark(benchmark_id: UUID, svc: BenchmarkService = Depends(get_service)):
    return await svc.get_benchmark(benchmark_id)


@router.post("", response_model=BenchmarkResponse, status_code=201)
async def create_benchmark(data: BenchmarkCreate, svc: BenchmarkService = Depends(get_service)):
    return await svc.create_benchmark(data)


@router.put("/{benchmark_id}", response_model=BenchmarkResponse)
async def update_benchmark(
    benchmark_id: UUID, data: BenchmarkUpdate, svc: BenchmarkService = Depends(get_service)
):
    return await svc.update_benchmark(benchmark_id, data)


@router.delete("/{benchmark_id}", status_code=204)
async def delete_benchmark(benchmark_id: UUID, svc: BenchmarkService = Depends(get_service)):
    await svc.delete_benchmark(benchmark_id)
