import json
import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import import_weekly_sqlite as importer  # noqa: E402
import rebuild_dashboard as dashboard  # noqa: E402


def test_dashboard_uses_latest_size_but_keeps_historical_weekly_size(tmp_path, monkeypatch):
    connection = sqlite3.connect(":memory:")
    importer.create_schema(connection)
    connection.executescript("""
        INSERT INTO fund_companies(id, name, size_category) VALUES(1, '甲公司', '10-20亿');
        INSERT INTO funds(id, company_id, name, strategy_type)
        VALUES(1, 1, '甲公司-500指增', 'index_500');
        INSERT INTO weekly_performances(
            fund_id, week_label, record_date, weekly_return, weekly_excess,
            ytd_return, ytd_excess, ytd_excess_drawdown, size_category
        ) VALUES
            (1, '0105-0109', '2026-01-09', 0.01, 0.005, 0.01, 0.005, 0.0, '10-20亿'),
            (1, '0112-0116', '2026-01-16', 0.02, 0.006, 0.03, 0.011, 0.0, '20-50亿');
    """)
    benchmark = tmp_path / "benchmark.json"
    benchmark.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(dashboard, "BENCHMARK_PATH", str(benchmark))

    result = dashboard.build_abs_data(connection.cursor())

    assert result["funds"][0]["size"] == "20~50亿"
    assert result["weeklyData"]["0105-0109"][0]["size"] == "10~20亿"
    assert result["weeklyData"]["0112-0116"][0]["size"] == "20~50亿"


def test_dashboard_metrics_module_contains_public_calculators():
    source = dashboard.METRICS_JS_PATH.read_text(encoding="utf-8")
    assert "function calculate(" in source
    assert "function excessDrawdownSeries(" in source
    assert "module.exports = DashboardMetrics" in source
