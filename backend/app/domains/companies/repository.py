from __future__ import annotations
"""Fund company data access layer."""

import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.companies.models import FundCompany


class CompanyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[FundCompany], int]:
        query = select(FundCompany)
        count_query = select(func.count(FundCompany.id))

        if status:
            query = query.where(FundCompany.status == status)
            count_query = count_query.where(FundCompany.status == status)
        if search:
            query = query.where(FundCompany.name.ilike(f"%{search}%"))
            count_query = count_query.where(FundCompany.name.ilike(f"%{search}%"))

        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(FundCompany.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_by_id(self, company_id: uuid.UUID) -> Optional[FundCompany]:
        result = await self.db.execute(
            select(FundCompany).where(FundCompany.id == company_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[FundCompany]:
        result = await self.db.execute(
            select(FundCompany).where(FundCompany.registration_code == code)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> FundCompany:
        company = FundCompany(**data)
        self.db.add(company)
        await self.db.flush()
        return company

    async def update(self, company: FundCompany, data: dict) -> FundCompany:
        for key, value in data.items():
            if value is not None:
                setattr(company, key, value)
        await self.db.flush()
        return company

    async def delete(self, company: FundCompany) -> None:
        await self.db.delete(company)
        await self.db.flush()
