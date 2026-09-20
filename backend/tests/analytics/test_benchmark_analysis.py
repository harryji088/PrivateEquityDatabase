import pytest

from analytics.benchmark_analysis import analyze_benchmarks


def test_first_week_and_early_rolling_window_use_year_start_anchor_without_future_data():
    benchmarks = {
        "CSI500": {
            "benchmark_key": "CSI500", "label": "中证500", "source_key": "中证500",
            "nav_by_date": {
                "20251231": 1.0, "20260109": 1.02, "20260116": 1.03,
                "20260123": 1.04, "20260130": 1.08, "20260206": 9.99,
            },
        },
    }
    first = analyze_benchmarks(
        benchmarks, ["2026-01-09"], "2026-01-09", None, [4, 12])
    assert first["benchmarks"][0]["weekly_return"] == pytest.approx(0.02)
    assert first["benchmarks"][0]["previous_nav_date"] == "20251231"

    dates = ["2026-01-09", "2026-01-16", "2026-01-23", "2026-01-30"]
    fourth = analyze_benchmarks(benchmarks, dates, dates[-1], dates[-2], [4, 12])
    assert fourth["benchmarks"][0]["rolling"]["weeks_4"]["return"] == pytest.approx(0.08)
    assert fourth["benchmarks"][0]["as_of_nav_date"] == "20260130"
