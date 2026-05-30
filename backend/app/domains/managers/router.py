from __future__ import annotations
"""Fund manager REST endpoints."""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.domains.managers.schemas import ManagerCreate, ManagerUpdate, ManagerResponse
from app.domains.managers.service import ManagerService
from app.api.v1.schemas import PaginatedResponse

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> ManagerService:
    return ManagerService(db)


@router.get("", response_model=PaginatedResponse[ManagerResponse])
async def list_managers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None),
    svc: ManagerService = Depends(get_service),
):
    items, total = await svc.list_managers(page, page_size, company_id, search)
    return PaginatedResponse(data=items, total=total, page=page, page_size=page_size)


@router.get("/{manager_id}", response_model=ManagerResponse)
async def get_manager(manager_id: UUID, svc: ManagerService = Depends(get_service)):
    return await svc.get_manager(manager_id)


@router.post("", response_model=ManagerResponse, status_code=201)
async def create_manager(data: ManagerCreate, svc: ManagerService = Depends(get_service)):
    return await svc.create_manager(data)


@router.put("/{manager_id}", response_model=ManagerResponse)
async def update_manager(
    manager_id: UUID, data: ManagerUpdate, svc: ManagerService = Depends(get_service)
):
    return await svc.update_manager(manager_id, data)


@router.delete("/{manager_id}", status_code=204)
async def delete_manager(manager_id: UUID, svc: ManagerService = Depends(get_service)):
    await svc.delete_manager(manager_id)
