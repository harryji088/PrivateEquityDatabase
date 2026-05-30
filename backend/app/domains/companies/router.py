from __future__ import annotations
"""Fund company REST endpoints."""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.domains.companies.schemas import (
    CompanyCreate,
    CompanyUpdate,
    CompanyResponse,
)
from app.domains.companies.service import CompanyService
from app.api.v1.schemas import PaginatedResponse

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> CompanyService:
    return CompanyService(db)


@router.get("", response_model=PaginatedResponse[CompanyResponse])
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(active|inactive|deregistered)$"),
    search: Optional[str] = Query(None),
    svc: CompanyService = Depends(get_service),
):
    items, total = await svc.list_companies(page, page_size, status, search)
    return PaginatedResponse(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: UUID,
    svc: CompanyService = Depends(get_service),
):
    return await svc.get_company(company_id)


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    data: CompanyCreate,
    svc: CompanyService = Depends(get_service),
):
    return await svc.create_company(data)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    data: CompanyUpdate,
    svc: CompanyService = Depends(get_service),
):
    return await svc.update_company(company_id, data)


@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: UUID,
    svc: CompanyService = Depends(get_service),
):
    await svc.delete_company(company_id)
