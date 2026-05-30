from __future__ import annotations
"""Fund REST endpoints."""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.domains.funds.schemas import FundCreate, FundUpdate, FundResponse
from app.domains.funds.service import FundService
from app.api.v1.schemas import PaginatedResponse

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> FundService:
    return FundService(db)


@router.get("", response_model=PaginatedResponse[FundResponse])
async def list_funds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_id: Optional[UUID] = Query(None),
    strategy_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    svc: FundService = Depends(get_service),
):
    items, total = await svc.list_funds(
        page, page_size, company_id, strategy_type, status, search
    )
    # Enrich with company/manager names
    enriched = []
    for fund in items:
        fund_dict = FundResponse.model_validate(fund).model_dump()
        if fund.company:
            fund_dict["company_name"] = fund.company.name
        if fund.manager:
            fund_dict["manager_name"] = fund.manager.name
        enriched.append(fund_dict)

    return PaginatedResponse(data=enriched, total=total, page=page, page_size=page_size)


@router.get("/{fund_id}", response_model=FundResponse)
async def get_fund(fund_id: UUID, svc: FundService = Depends(get_service)):
    fund = await svc.get_fund(fund_id)
    fund_dict = FundResponse.model_validate(fund).model_dump()
    if fund.company:
        fund_dict["company_name"] = fund.company.name
    if fund.manager:
        fund_dict["manager_name"] = fund.manager.name
    return fund_dict


@router.post("", response_model=FundResponse, status_code=201)
async def create_fund(data: FundCreate, svc: FundService = Depends(get_service)):
    fund = await svc.create_fund(data)
    fund_dict = FundResponse.model_validate(fund).model_dump()
    if fund.company:
        fund_dict["company_name"] = fund.company.name
    if fund.manager:
        fund_dict["manager_name"] = fund.manager.name
    return fund_dict


@router.put("/{fund_id}", response_model=FundResponse)
async def update_fund(
    fund_id: UUID, data: FundUpdate, svc: FundService = Depends(get_service)
):
    fund = await svc.update_fund(fund_id, data)
    fund_dict = FundResponse.model_validate(fund).model_dump()
    if fund.company:
        fund_dict["company_name"] = fund.company.name
    if fund.manager:
        fund_dict["manager_name"] = fund.manager.name
    return fund_dict


@router.delete("/{fund_id}", status_code=204)
async def delete_fund(fund_id: UUID, svc: FundService = Depends(get_service)):
    await svc.delete_fund(fund_id)
