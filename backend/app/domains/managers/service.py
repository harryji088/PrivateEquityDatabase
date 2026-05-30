from __future__ import annotations
"""Fund manager business logic."""

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.domains.managers.repository import ManagerRepository
from app.domains.managers.schemas import ManagerCreate, ManagerUpdate


class ManagerService:
    def __init__(self, db: AsyncSession):
        self.repo = ManagerRepository(db)

    async def list_managers(
        self, page: int = 1, page_size: int = 20,
        company_id: Optional[uuid.UUID] = None, search: Optional[str] = None,
    ):
        items, total = await self.repo.list(page, page_size, company_id, search)
        return items, total

    async def get_manager(self, manager_id: uuid.UUID):
        manager = await self.repo.get_by_id(manager_id)
        if not manager:
            raise NotFoundException(f"Manager {manager_id} not found")
        return manager

    async def create_manager(self, data: ManagerCreate):
        return await self.repo.create(data.model_dump())

    async def update_manager(self, manager_id: uuid.UUID, data: ManagerUpdate):
        manager = await self.get_manager(manager_id)
        return await self.repo.update(manager, data.model_dump(exclude_unset=True))

    async def delete_manager(self, manager_id: uuid.UUID):
        manager = await self.get_manager(manager_id)
        await self.repo.delete(manager)
