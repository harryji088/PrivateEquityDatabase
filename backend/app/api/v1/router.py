"""Aggregate all v1 domain routers."""

from fastapi import APIRouter

from app.domains.funds.router import router as funds_router
from app.domains.companies.router import router as companies_router
from app.domains.managers.router import router as managers_router
from app.domains.nav.router import router as nav_router
from app.domains.metrics.router import router as metrics_router
from app.domains.benchmarks.router import router as benchmarks_router
from app.domains.comparison.router import router as comparison_router
from app.domains.import_export.router import router as import_export_router
from app.domains.reports.router import router as reports_router

api_router = APIRouter()

api_router.include_router(funds_router, prefix="/funds", tags=["Funds"])
api_router.include_router(companies_router, prefix="/companies", tags=["Companies"])
api_router.include_router(managers_router, prefix="/managers", tags=["Managers"])
api_router.include_router(nav_router, prefix="/nav", tags=["NAV"])
api_router.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])
api_router.include_router(benchmarks_router, prefix="/benchmarks", tags=["Benchmarks"])
api_router.include_router(comparison_router, prefix="/comparison", tags=["Comparison"])
api_router.include_router(import_export_router, prefix="/import", tags=["Import/Export"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
