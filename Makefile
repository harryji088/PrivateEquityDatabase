PYTHON ?= $(if $(wildcard .venv/bin/python),$(CURDIR)/.venv/bin/python,python3)

.PHONY: import-weekly import-weekly-full update-benchmark update-style rebuild-dashboard update-data test test-js lint ci check analytics weekly-report weekly-report-validate update-all

# ── Data pipeline (SQLite + self-contained dashboard) ──

import-weekly:
	cd backend && "$(PYTHON)" scripts/import_weekly_sqlite.py

import-weekly-full:
	cd backend && "$(PYTHON)" scripts/import_weekly_sqlite.py --full

update-benchmark:
	cd backend && "$(PYTHON)" scripts/update_benchmark.py

update-style:
	cd backend && "$(PYTHON)" scripts/update_style_indices.py

rebuild-dashboard:
	cd backend && "$(PYTHON)" scripts/rebuild_dashboard.py

# Full pipeline. NOTE: update-benchmark MUST run before import-weekly —
# import computes stock_long excess returns from benchmark_nav.json,
# so it needs the freshly fetched benchmark data.
update-data:
	$(MAKE) update-benchmark
	$(MAKE) import-weekly
	$(MAKE) rebuild-dashboard
	@echo "✅ Data pipeline complete"

# ── Tests (core calculation logic) ──

test:
	cd backend && "$(PYTHON)" -m pytest

test-js:
	node --test backend/tests_js/*.test.js

lint:
	cd backend && "$(PYTHON)" -m ruff check .

ci: test test-js lint

check: test test-js lint weekly-report-validate

# ── Offline weekly report (read-only SQLite + local benchmark JSON) ──

analytics: weekly-report-validate

weekly-report:
	cd backend && "$(PYTHON)" scripts/generate_weekly_report.py --print-summary

weekly-report-validate:
	cd backend && "$(PYTHON)" scripts/generate_weekly_report.py --validate-only --print-summary

# Kept separate from update-data so the established dashboard pipeline remains unchanged.
update-all:
	$(MAKE) update-data
	$(MAKE) update-style
	$(MAKE) weekly-report
