from __future__ import annotations
"""Fund data access layer."""

import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domains.funds.models import Fund


class FundRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        company_id: Optional[uuid.UUID] = None,
        strategy_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Fund], int]:
        query = select(Fund).options(
            joinedload(Fund.company),
            joinedload(Fund.manager),
        )
        count_query = select(func.count(Fund.id))

        filters = []
        if company_id:
            filters.append(Fund.company_id == company_id)
        if strategy_type:
            filters.append(Fund.strategy_type == strategy_type)
        if status:
            filters.append(Fund.status == status)
        if search:
            filters.append(Fund.name.ilike(f"%{search}%"))

        for f in filters:
            query = query.where(f)
            count_query = count_query.where(f)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.order_by(Fund.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)

        result = await self.db.execute(query)
        return list(result.unique().scalars().all()), total

    async def get_by_id(self, fund_id: uuid.UUID) -> Optional[Fund]:
        result = await self.db.execute(
            select(Fund)
            .options(joinedload(Fund.company), joinedload(Fund.manager))
            .where(Fund.id == fund_id)
        )
        return result.unique().scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[Fund]:
        result = await self.db.execute(select(Fund).where(Fund.code == code))
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Fund:
        fund = Fund(**data)
        self.db.add(fund)
        await self.db.flush()
        # Refresh to load relationships
        return await self.get_by_id(fund.id)

    async def update(self, fund: Fund, data: dict) -> Fund:
        for key, value in data.items():
            if value is not None:
                setattr(fund, key, value)
        await self.db.flush()
        return await self.get_by_id(fund.id)

    async def delete(self, fund: Fund) -> None:
        await self.db.delete(fund)
        await self.db.flush()
