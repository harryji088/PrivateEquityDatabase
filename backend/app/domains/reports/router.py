from __future__ import annotations
"""Report generation REST endpoints (stub)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/templates")
async def list_templates():
    return {"message": "Reports coming in Phase 3", "data": []}


@router.post("/generate")
async def generate_report():
    return {"message": "Report generation coming in Phase 3"}
