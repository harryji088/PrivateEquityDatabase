# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A quantitative private equity (量化私募) fund performance database platform. Ingests weekly Excel rankings from "点睛业绩放送", computes cumulative NAV (年初=1.0), and provides interactive dashboards for strategy comparison, ranking, and benchmark overlay.

## Common Commands

```bash
# Backend
make backend-dev          # uvicorn --reload on port 8000
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (Vite dev server on port 5173, proxies /api → localhost:8000)
make frontend-dev
cd frontend && npm run dev

# Database (PostgreSQL via Docker)
make db-up                # docker compose up -d db redis
make migrate              # alembic upgrade head
make seed                 # seed_data.py — generates 50+ fake funds with 2yr NAV history

# Import real weekly data (SQLite, self-contained)
cd backend && python scripts/import_weekly_sqlite.py

# Tests
make test                 # cd backend && pytest (asyncio_mode=auto)

# Lint (backend uses ruff, frontend uses eslint)
cd backend && ruff check .
cd frontend && npm run lint

# Full Docker stack
make docker-up            # postgres + redis + backend
```

## Architecture

### Dual Data Paths

1. **SQLite + static HTML** (`cc_data.sqlite3` → `dashboard.html`): The primary working path. Real weekly data from 19 Excel files in `data/` is parsed by `backend/scripts/import_weekly_sqlite.py` into a local SQLite DB. A standalone `dashboard.html` (~920KB) embeds all data as a `var DATA = {...}` JSON blob and renders charts with ECharts 5 (CDN-loaded). No server needed — open the HTML file directly.

2. **PostgreSQL + FastAPI + React SPA** (`backend/` + `frontend/`): Full-stack platform for CRUD management of funds, companies, managers, NAV data, and performance analytics. Currently scaffolded with all endpoints working but not yet populated with the real weekly data.

### Dashboard HTML (`dashboard.html`)

A single self-contained file with 6 sections:
- **#1 Strategy chart**: 7 strategy average curves + 6 benchmark index lines (thick dashed)
- **#2 Grid chart**: Filter by strategy/size, overlay selectable benchmark, shows top 30 funds
- **#3 Weekly return ranking**: Interactive table by week/strategy/size, with bar charts and percentile
- **#4 YTD ranking**: Cumulative NAV and YTD return rankings
- **#5 Single fund picker**: Multi-select fund comparison with benchmark overlay
- **#6 Cumulative NAV matrix**: Full fund × week NAV heatmap with search

`makeBenchSeries(bname, showSymbol)` creates benchmark series. Benchmark data is daily (95 points) but resampled to 19 weekly dates matching fund record dates via `DATA.dates` lookup. Charts #1/#5 use `trigger:'axis'` tooltips (no symbol needed). Chart #2 uses `trigger:'item'` (needs `showSymbol=true` for diamond markers on benchmark).

### Backend Domain Pattern

Each domain follows a strict 4-layer pattern in `backend/app/domains/<name>/`:

| File | Purpose |
|------|---------|
| `models.py` | SQLAlchemy 2.0 ORM models (declarative, `Mapped[type]` annotations) |
| `schemas.py` | Pydantic v2 request/response schemas |
| `service.py` | Business logic, takes `AsyncSession` |
| `router.py` | FastAPI `APIRouter`, dependency-injects service via `Depends(get_service)` |

Domains: `funds`, `companies`, `managers`, `nav`, `metrics`, `benchmarks`, `comparison`, `import_export`, `reports`

Standard CRUD endpoint pattern (exemplified by `funds`):
- `GET /` — paginated list with optional filters (search, strategy_type, status)
- `GET /{id}` — single item
- `POST /` — create (201)
- `PUT /{id}` — update
- `DELETE /{id}` — delete (204)

Shared dependencies in `backend/app/dependencies.py`: `pagination()` and `date_range_filter()`.

### Key Data Model (from SQLite)

```
fund_companies: id, name, size_category
funds: id, company_id → fund_companies, strategy_type, name (format: "{company}-{策略名}")
weekly_performances: id, fund_id → funds, week_label, record_date, rank,
  weekly_return, weekly_excess, ytd_return, ytd_excess, ytd_drawdown,
  ann_return, ann_vol, max_drawdown, sharpe, size_category
  — UNIQUE(fund_id, week_label)
benchmark_index: id, symbol, name
benchmark_index_data: id, index_id → benchmark_index, trade_date, close_price
```

Cumulative NAV = `1.0 + ytd_return` (using "今年以来收益率" column). Missing weeks are left empty, not filled to 1.0.

Strategy mapping:
```
量化选股 → stock_long, 市场中性 → market_neutral, 500指增 → index_500,
1000指增 → index_1000, 300指增 → index_300, 2000指增 → index_2000, A500指增 → index_a500
```

Strategy-to-benchmark mapping for excess return:
```
量化选股 → 中证1000, 市场中性 → 沪深300, 500指增 → 中证500,
1000指增 → 中证1000, 300指增 → 沪深300, 2000指增 → 中证2000, A500指增 → A500
```

### Frontend Stack

- React 19 + TypeScript + Vite 8
- Ant Design 6 for UI components
- ECharts 6 via `echarts-for-react` for charts
- TanStack Query (React Query) for server state
- Zustand for client-side state
- React Router 7 for routing
- Axios client at `frontend/src/api/client.ts` — base URL auto-proxied to backend in dev

### Data Pipeline

1. 19 weekly Excel files in `data/` with 7 strategy sheets each (varying 14-17 column layouts)
2. `backend/scripts/import_weekly_sqlite.py` parses them, normalizes size categories (`~` → `-`), creates SQLite DB
3. `cumulative_nav_weekly.csv` exports the merged time series (370 funds × 19 weeks)
4. `dashboard.html` generator embeds all data + benchmark daily NAV series
5. Benchmark data fetched via AKShare `stock_zh_index_daily` (sina source, works through VPN)

### Python 3.9 Compatibility

The SQLite import script targets Python 3.9. Must use:
- `from __future__ import annotations`
- `Optional[X]` instead of `X | None`
- `List[X]`, `Dict[X, Y]` from `typing`

### Git/Network Notes

- Proxy on port 7890 (Clash) for GitHub access: `git -c http.proxy=http://127.0.0.1:7890`
- Chinese data sources (AKShare) need direct connection (no proxy)
- `.gitignore` excludes `*.sqlite3*` (including WAL/SHM), `*.csv` (except `data/*.csv`)
