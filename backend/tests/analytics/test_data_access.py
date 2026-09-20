import json
import sqlite3

import pytest

from analytics.data_access import load_observations, load_style_nav
from analytics.schemas import AnalyticsError


def test_load_observations_reports_missing_required_column_as_analytics_error():
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE fund_companies (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE funds (id INTEGER PRIMARY KEY, company_id INTEGER, strategy_type TEXT);
        CREATE TABLE weekly_performances (
            id INTEGER PRIMARY KEY, fund_id INTEGER, week_label TEXT, record_date TEXT,
            weekly_return REAL, weekly_excess REAL, ytd_return REAL, ytd_excess REAL
        );
    """)
    with pytest.raises(AnalyticsError, match="ytd_excess_drawdown"):
        load_observations(
            connection, {"index_500": {"label": "500指增", "benchmark_key": "CSI500"}})


def test_load_style_nav_rejects_cache_identity_mismatch(tmp_path):
    path = tmp_path / "style.json"
    path.write_text(json.dumps({
        "测试指数": {
            "label": "测试指数", "wind_code": "000001.CSI", "csindex_code": "WRONG",
            "dates": ["20260101"], "navs": [1.0],
        },
    }), encoding="utf-8")
    config = {
        "TEST": {
            "label": "测试指数", "source_key": "测试指数",
            "wind_code": "000001.CSI", "csindex_code": "000001",
        },
    }

    with pytest.raises(AnalyticsError, match="mismatched csindex_code"):
        load_style_nav(path, config)
