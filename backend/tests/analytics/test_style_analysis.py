import pytest

from analytics.style_analysis import analyze_style_proxies


def _series(values):
    return {"nav_by_date": values}


def _proxy():
    return {
        "key": "growth_value", "label": "成长 - 价值", "category": "成长价值",
        "long_key": "GROWTH", "short_key": "VALUE",
        "positive_label": "成长相对占优", "negative_label": "价值相对占优",
    }


def test_style_spread_uses_endpoint_returns_not_sum_of_weekly_spreads():
    sources = {
        "GROWTH": _series({
            "20251231": 1.0, "20260109": 1.10, "20260116": 1.21,
            "20260123": 1.10, "20260130": 1.21,
        }),
        "VALUE": _series({
            "20251231": 1.0, "20260109": 1.05, "20260116": 1.1025,
            "20260123": 1.21, "20260130": 1.21,
        }),
    }
    dates = ["2026-01-09", "2026-01-16", "2026-01-23", "2026-01-30"]
    result = analyze_style_proxies(sources, [_proxy()], dates, dates[-1], dates[-2], [4, 12], 12)
    item = result["proxies"][0]

    assert item["weekly"]["spread"] == pytest.approx(0.10)
    assert item["weekly"]["direction"] == "成长相对占优"
    assert item["rolling"]["weeks_4"]["spread"] == pytest.approx(0.0)
    assert item["rolling"]["weeks_12"]["status"] == "insufficient_history"
    assert item["stability"]["switch_count"] == 2
    assert item["stability"]["current_streak_weeks"] == 1


def test_style_spread_is_incomplete_when_legs_use_different_actual_dates():
    sources = {
        "GROWTH": _series({"20251231": 1.0, "20260109": 1.10}),
        "VALUE": _series({"20251230": 1.0, "20260108": 1.05}),
    }
    result = analyze_style_proxies(
        sources, [_proxy()], ["2026-01-09"], "2026-01-09", None, [4, 12], 12)
    weekly = result["proxies"][0]["weekly"]

    assert weekly["spread"] is None
    assert weekly["status"] == "incomplete"
    assert weekly["reason"] == "两条指数实际取值日期不一致"


def test_style_category_conclusion_marks_short_term_reversal_without_claiming_confirmation():
    sources = {
        "GROWTH": _series({
            "20251231": 1.0, "20260109": 1.0, "20260116": 1.0,
            "20260123": 1.0, "20260130": 1.20,
        }),
        "VALUE": _series({
            "20251231": 1.0, "20260109": 1.10, "20260116": 1.21,
            "20260123": 1.331, "20260130": 1.331,
        }),
    }
    dates = ["2026-01-09", "2026-01-16", "2026-01-23", "2026-01-30"]
    result = analyze_style_proxies(sources, [_proxy()], dates, dates[-1], dates[-2], [4, 12], 12)
    conclusion = result["summary"]["category_conclusions"][0]

    assert conclusion["weekly"]["label"] == "成长相对占优"
    assert conclusion["weeks_4"]["label"] == "价值相对占优"
    assert conclusion["trend_comment"] == "本周与近4周方向相反，尚待确认"


def test_style_rejects_two_synchronously_stale_legs_instead_of_reporting_flat():
    sources = {
        "GROWTH": _series({"20251231": 1.0, "20260109": 1.10}),
        "VALUE": _series({"20251231": 1.0, "20260109": 1.05}),
    }
    result = analyze_style_proxies(
        sources, [_proxy()], ["2026-01-09", "2026-01-16"],
        "2026-01-16", "2026-01-09", [4, 12], 12,
        max_staleness_days=4)
    weekly = result["proxies"][0]["weekly"]

    assert weekly["status"] == "incomplete"
    assert weekly["spread"] is None
    assert "滞后" in weekly["reason"]
    assert result["summary"]["available_proxy_count"] == 0
    assert result["summary"]["category_conclusions"][0]["weekly"]["state"] == "incomplete"


def test_style_neutral_threshold_and_category_completeness_prevent_strong_headline():
    second_proxy = dict(
        _proxy(), key="growth_value_2", label="另一组成长 - 价值",
        long_key="GROWTH_2", short_key="VALUE_2")
    sources = {
        "GROWTH": _series({"20251231": 1.0, "20260109": 1.0004}),
        "VALUE": _series({"20251231": 1.0, "20260109": 1.0}),
    }
    result = analyze_style_proxies(
        sources, [_proxy(), second_proxy], ["2026-01-09"],
        "2026-01-09", None, [4, 12], 12,
        neutral_spread_threshold=0.0005)

    assert result["proxies"][0]["weekly"]["direction"] == "相对持平"
    conclusion = result["summary"]["category_conclusions"][0]["weekly"]
    assert conclusion["state"] == "incomplete"
    assert conclusion["label"] == "数据不完整（1/2 可用）"
    assert "成长相对占优" not in result["summary"]["headline"]


def test_style_first_week_uses_year_start_anchor_and_ignores_future_observations():
    sources = {
        "GROWTH": _series({
            "20251231": 1.0, "20260109": 1.10, "20260123": 2.0,
        }),
        "VALUE": _series({
            "20251231": 1.0, "20260109": 1.05, "20260123": 0.5,
        }),
    }
    result = analyze_style_proxies(
        sources, [_proxy()], ["2026-01-09"], "2026-01-09", None, [4, 12], 12)
    weekly = result["proxies"][0]["weekly"]

    assert weekly["spread"] == pytest.approx(0.05)
    assert weekly["long_end_nav_date"] == "20260109"
    assert weekly["short_end_nav_date"] == "20260109"
