.PHONY: import-weekly update-benchmark rebuild-dashboard update-data test

# ── Data pipeline (SQLite + self-contained dashboard) ──

import-weekly:
	cd backend && python3 scripts/import_weekly_sqlite.py

update-benchmark:
	cd backend && python3 scripts/update_benchmark.py

rebuild-dashboard:
	cd backend && python3 scripts/rebuild_dashboard.py

# Full pipeline. NOTE: update-benchmark MUST run before import-weekly —
# import computes stock_long excess returns from benchmark_nav.json,
# so it needs the freshly fetched benchmark data.
update-data: update-benchmark import-weekly rebuild-dashboard
	@echo "✅ Data pipeline complete"

# ── Tests (core calculation logic) ──

test:
	cd backend && python3 -m pytest
