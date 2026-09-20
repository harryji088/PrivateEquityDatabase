.PHONY: import-weekly update-benchmark update-style rebuild-dashboard update-data test analytics weekly-report weekly-report-validate update-all

# ── Data pipeline (SQLite + self-contained dashboard) ──

import-weekly:
	cd backend && python3 scripts/import_weekly_sqlite.py

update-benchmark:
	cd backend && python3 scripts/update_benchmark.py

update-style:
	cd backend && python3 scripts/update_style_indices.py

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

# ── Offline weekly report (read-only SQLite + local benchmark JSON) ──

analytics: weekly-report-validate

weekly-report:
	cd backend && python3 scripts/generate_weekly_report.py --print-summary

weekly-report-validate:
	cd backend && python3 scripts/generate_weekly_report.py --validate-only --print-summary

# Kept separate from update-data so the established dashboard pipeline remains unchanged.
update-all:
	$(MAKE) update-data
	$(MAKE) update-style
	$(MAKE) weekly-report
