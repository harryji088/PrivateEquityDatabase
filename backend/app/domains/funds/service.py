from __future__ import annotations
"""Fund business logic."""

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ConflictException
from app.domains.funds.repository import FundRepository
from app.domains.funds.schemas import FundCreate, FundUpdate


class FundService:
    def __init__(self, db: AsyncSession):
        self.repo = FundRepository(db)

    async def list_funds(
        self,
        page: int = 1,
        page_size: int = 20,
        company_id: Optional[uuid.UUID] = None,
        strategy_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ):
        items, total = await self.repo.list(
            page, page_size, company_id, strategy_type, status, search
        )
        return items, total

    async def get_fund(self, fund_id: uuid.UUID):
        fund = await self.repo.get_by_id(fund_id)
        if not fund:
            raise NotFoundException(f"Fund {fund_id} not found")
        return fund

    async def create_fund(self, data: FundCreate):
        if data.code:
            existing = await self.repo.get_by_code(data.code)
            if existing:
                raise ConflictException(f"Fund with code {data.code} already exists")
        return await self.repo.create(data.model_dump())

    async def update_fund(self, fund_id: uuid.UUID, data: FundUpdate):
        fund = await self.get_fund(fund_id)
        return await self.repo.update(fund, data.model_dump(exclude_unset=True))

    async def delete_fund(self, fund_id: uuid.UUID):
        fund = await self.get_fund(fund_id)
        await self.repo.delete(fund)
