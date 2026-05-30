from __future__ import annotations
"""NAV data REST endpoints."""

from uuid import UUID
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.domains.nav.schemas import (
    NavDataCreate, NavDataUpdate, NavDataResponse, NavDataBulkCreate,
)
from app.domains.nav.service import NavService
from app.api.v1.schemas import PaginatedResponse

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> NavService:
    return NavService(db)


@router.get("", response_model=PaginatedResponse[NavDataResponse])
async def list_nav(
    fund_id: UUID = Query(...),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    svc: NavService = Depends(get_service),
):
    items, total = await svc.list_nav(fund_id, start_date, end_date, page, page_size)
    return PaginatedResponse(data=items, total=total, page=page, page_size=page_size)


@router.get("/latest")
async def get_latest_nav(
    fund_ids: str = Query(..., description="Comma-separated fund UUIDs"),
    svc: NavService = Depends(get_service),
):
    """Get the latest NAV for multiple funds."""
    ids = [UUID(id_str.strip()) for id_str in fund_ids.split(",") if id_str.strip()]
    result = {}
    for fid in ids:
        items, _ = await svc.list_nav(fid, page=1, page_size=1)
        if items:
            result[str(fid)] = items[0]
        else:
            result[str(fid)] = None
    return {"data": [NavDataResponse.model_validate(r).model_dump() if r else None for r in [result.get(str(fid)) for fid in ids]]}


@router.get("/{nav_id}", response_model=NavDataResponse)
async def get_nav(nav_id: int, svc: NavService = Depends(get_service)):
    return await svc.get_nav(nav_id)


@router.post("", response_model=NavDataResponse, status_code=201)
async def create_nav(data: NavDataCreate, svc: NavService = Depends(get_service)):
    return await svc.create_nav(data)


@router.post("/bulk")
async def bulk_create_nav(
    data: NavDataBulkCreate, svc: NavService = Depends(get_service)
):
    count = await svc.bulk_create_nav(data)
    return {"message": f"Processed {count} records", "count": count}


@router.put("/{nav_id}", response_model=NavDataResponse)
async def update_nav(
    nav_id: int, data: NavDataUpdate, svc: NavService = Depends(get_service)
):
    return await svc.update_nav(nav_id, data)


@router.delete("/{nav_id}", status_code=204)
async def delete_nav(nav_id: int, svc: NavService = Depends(get_service)):
    await svc.delete_nav(nav_id)
