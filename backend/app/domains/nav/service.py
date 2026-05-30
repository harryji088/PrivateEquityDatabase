from __future__ import annotations
"""NAV data business logic with daily return auto-calculation."""

import uuid
from datetime import date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ConflictException
from app.domains.nav.repository import NavRepository
from app.domains.nav.schemas import NavDataCreate, NavDataUpdate, NavDataBulkCreate


class NavService:
    def __init__(self, db: AsyncSession):
        self.repo = NavRepository(db)

    def _calc_daily_return(self, current_nav: float, previous_nav: float) -> float:
        """Calculate daily return: (NAV_t / NAV_t-1) - 1."""
        if previous_nav == 0:
            return 0.0
        return (current_nav / previous_nav) - 1

    async def list_nav(
        self,
        fund_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 100,
    ):
        return await self.repo.list(fund_id, start_date, end_date, page, page_size)

    async def get_nav(self, nav_id: int):
        nav = await self.repo.get_by_id(nav_id)
        if not nav:
            raise NotFoundException(f"NAV record {nav_id} not found")
        return nav

    async def create_nav(self, data: NavDataCreate) -> dict:
        """Create a NAV record with automatic daily return calculation."""
        # Check for duplicate
        existing = await self.repo.get_by_date(data.fund_id, data.date)
        if existing:
            raise ConflictException(
                f"NAV for fund {data.fund_id} on {data.date} already exists"
            )

        # Calculate daily return
        daily_return = None
        prev = await self.repo.get_previous_nav(data.fund_id, data.date)
        if prev:
            daily_return = self._calc_daily_return(data.nav, prev.nav)

        record = data.model_dump()
        record["daily_return"] = daily_return
        nav = await self.repo.create(record)
        return nav

    async def bulk_create_nav(self, data: NavDataBulkCreate) -> int:
        """Bulk insert NAV records. Skips duplicates, calculates daily returns."""
        count = 0
        records = []
        for rec in data.records:
            existing = await self.repo.get_by_date(rec.fund_id, rec.date)
            if existing:
                continue

            daily_return = None
            prev = await self.repo.get_previous_nav(rec.fund_id, rec.date)
            if prev:
                daily_return = self._calc_daily_return(rec.nav, prev.nav)

            record_dict = rec.model_dump()
            record_dict["daily_return"] = daily_return
            records.append(record_dict)
            count += 1

        if records:
            await self.repo.bulk_upsert(records)
        return count

    async def update_nav(self, nav_id: int, data: NavDataUpdate) -> dict:
        nav = await self.get_nav(nav_id)
        updated = data.model_dump(exclude_unset=True)

        # Recalculate daily return if NAV changed
        if "nav" in updated:
            prev = await self.repo.get_previous_nav(nav.fund_id, nav.date)
            if prev:
                updated["daily_return"] = self._calc_daily_return(
                    updated["nav"], prev.nav
                )

        return await self.repo.update(nav, updated)

    async def delete_nav(self, nav_id: int):
        nav = await self.get_nav(nav_id)
        await self.repo.delete(nav)

    async def get_fund_nav_range(
        self, fund_id: uuid.UUID, start_date: date, end_date: date
    ):
        """Get NAV data for analytics (ordered by date ascending)."""
        return await self.repo.get_nav_range(fund_id, start_date, end_date)
