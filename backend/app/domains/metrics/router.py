from __future__ import annotations
"""Performance metrics REST endpoints (stub — full implementation in Phase 2)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/{fund_id}")
async def get_fund_metrics(fund_id: str):
    return {"message": "Metrics engine coming in Phase 2", "fund_id": fund_id}


@router.get("/ranking")
async def get_ranking():
    return {"message": "Ranking coming in Phase 2"}
