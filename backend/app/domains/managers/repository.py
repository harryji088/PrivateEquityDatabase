from __future__ import annotations
"""Fund manager data access layer."""

import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.managers.models import FundManager


class ManagerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self, page: int = 1, page_size: int = 20,
        company_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> tuple[list[FundManager], int]:
        query = select(FundManager)
        count_query = select(func.count(FundManager.id))

        if company_id:
            query = query.where(FundManager.company_id == company_id)
            count_query = count_query.where(FundManager.company_id == company_id)
        if search:
            query = query.where(FundManager.name.ilike(f"%{search}%"))
            count_query = count_query.where(FundManager.name.ilike(f"%{search}%"))

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.order_by(FundManager.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(self, manager_id: uuid.UUID) -> Optional[FundManager]:
        result = await self.db.execute(
            select(FundManager).where(FundManager.id == manager_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> FundManager:
        manager = FundManager(**data)
        self.db.add(manager)
        await self.db.flush()
        return manager

    async def update(self, manager: FundManager, data: dict) -> FundManager:
        for key, value in data.items():
            if value is not None:
                setattr(manager, key, value)
        await self.db.flush()
        return manager

    async def delete(self, manager: FundManager) -> None:
        await self.db.delete(manager)
        await self.db.flush()
