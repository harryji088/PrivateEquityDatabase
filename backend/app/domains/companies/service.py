from __future__ import annotations
"""Fund company business logic."""

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ConflictException
from app.domains.companies.repository import CompanyRepository
from app.domains.companies.schemas import CompanyCreate, CompanyUpdate


class CompanyService:
    def __init__(self, db: AsyncSession):
        self.repo = CompanyRepository(db)

    async def list_companies(
        self, page: int = 1, page_size: int = 20,
        status: Optional[str] = None, search: Optional[str] = None,
    ):
        items, total = await self.repo.list(page, page_size, status, search)
        return items, total

    async def get_company(self, company_id: uuid.UUID):
        company = await self.repo.get_by_id(company_id)
        if not company:
            raise NotFoundException(f"Company {company_id} not found")
        return company

    async def create_company(self, data: CompanyCreate):
        if data.registration_code:
            existing = await self.repo.get_by_code(data.registration_code)
            if existing:
                raise ConflictException(
                    f"Company with code {data.registration_code} already exists"
                )
        return await self.repo.create(data.model_dump())

    async def update_company(self, company_id: uuid.UUID, data: CompanyUpdate):
        company = await self.get_company(company_id)
        update_data = data.model_dump(exclude_unset=True)
        return await self.repo.update(company, update_data)

    async def delete_company(self, company_id: uuid.UUID):
        company = await self.get_company(company_id)
        await self.repo.delete(company)
