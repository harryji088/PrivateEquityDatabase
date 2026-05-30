from __future__ import annotations
"""Fund comparison REST endpoints (stub)."""

from fastapi import APIRouter

router = APIRouter()


@router.post("")
async def compare_funds():
    return {"message": "Comparison engine coming in Phase 2"}
