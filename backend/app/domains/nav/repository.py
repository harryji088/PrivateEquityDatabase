from __future__ import annotations
"""NAV data access layer."""

import uuid
from datetime import date
from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.nav.models import NavData


class NavRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self,
        fund_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[list[NavData], int]:
        query = select(NavData).where(NavData.fund_id == fund_id)
        count_query = select(func.count(NavData.id)).where(NavData.fund_id == fund_id)

        if start_date:
            query = query.where(NavData.date >= start_date)
            count_query = count_query.where(NavData.date >= start_date)
        if end_date:
            query = query.where(NavData.date <= end_date)
            count_query = count_query.where(NavData.date <= end_date)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.order_by(NavData.date.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_date(self, fund_id: uuid.UUID, nav_date: date) -> Optional[NavData]:
        result = await self.db.execute(
            select(NavData).where(
                and_(NavData.fund_id == fund_id, NavData.date == nav_date)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, nav_id: int) -> Optional[NavData]:
        result = await self.db.execute(select(NavData).where(NavData.id == nav_id))
        return result.scalar_one_or_none()

    async def get_previous_nav(self, fund_id: uuid.UUID, before_date: date) -> Optional[NavData]:
        """Get the most recent NAV before the given date, for daily return calc."""
        result = await self.db.execute(
            select(NavData)
            .where(and_(NavData.fund_id == fund_id, NavData.date < before_date))
            .order_by(NavData.date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_nav_range(
        self, fund_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[NavData]:
        """Get all NAV within a date range, ordered by date ascending."""
        result = await self.db.execute(
            select(NavData)
            .where(
                and_(
                    NavData.fund_id == fund_id,
                    NavData.date >= start_date,
                    NavData.date <= end_date,
                )
            )
            .order_by(NavData.date.asc())
        )
        return list(result.scalars().all())

    async def create(self, data: dict) -> NavData:
        nav = NavData(**data)
        self.db.add(nav)
        await self.db.flush()
        return nav

    async def bulk_upsert(self, records: list[dict]) -> int:
        """Bulk insert or update NAV records. Returns count of records processed."""
        count = 0
        for record in records:
            nav_data = NavData(**record)
            self.db.add(nav_data)
            count += 1
        await self.db.flush()
        return count

    async def update(self, nav: NavData, data: dict) -> NavData:
        for key, value in data.items():
            if value is not None:
                setattr(nav, key, value)
        await self.db.flush()
        return nav

    async def delete(self, nav: NavData) -> None:
        await self.db.delete(nav)
        await self.db.flush()
