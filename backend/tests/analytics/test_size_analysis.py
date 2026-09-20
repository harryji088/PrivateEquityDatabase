from datetime import date

import pytest

from analytics.schemas import WeeklyObservation
from analytics.size_analysis import analyze_size_groups, normalize_size_category

STRATEGIES = {"index_500": {"label": "500指增", "benchmark_key": "CSI500"}}
CONFIG = {
    "enabled": True,
    "min_size_group_sample_size": 2,
    "size_effect_min_gap": 0.002,
    "groups": {
        "large": {"label": "百亿以上", "categories": ["100亿以上"]},
        "medium": {"label": "20~100亿", "categories": ["20~50亿", "50~100亿"]},
        "small": {"label": "20亿以下", "categories": ["0~5亿", "5~10亿", "10~20亿"]},
    },
}


def _observation(manager_id, size_category, excess, weekly_return=None):
    return WeeklyObservation(
        as_of_date=date(2026, 9, 11), week_label="0907-0911",
        manager_id=manager_id, manager_name=f"管理人{manager_id}",
        strategy_key="index_500", strategy_label="500指增",
        weekly_return=excess if weekly_return is None else weekly_return,
        weekly_excess=excess, ytd_return=None, ytd_excess=None,
        ytd_excess_drawdown=None, source_row_id=str(manager_id),
        size_category=size_category,
    )


def _analyze(rows, config=None):
    return analyze_size_groups(rows, "2026-09-11", STRATEGIES, config or CONFIG)


def test_normalize_size_category_unifies_hyphen_tilde_and_fullwidth_tilde():
    assert normalize_size_category("50-100亿") == "50~100亿"
    assert normalize_size_category("50~100亿") == "50~100亿"
    assert normalize_size_category("20～50亿") == "20~50亿"
    assert normalize_size_category(" 0-5亿 ") == "0~5亿"


def test_normalize_missing_unknown_and_unrecognized_values_to_unknown():
    assert normalize_size_category(None) == "未知"
    assert normalize_size_category("") == "未知"
    assert normalize_size_category("未知") == "未知"
    assert normalize_size_category("约30亿") == "未知"


def test_strategy_rows_are_assigned_to_configured_aggregate_groups():
    rows = [
        _observation(1, "100亿以上", 0.01), _observation(2, "100亿以上", 0.02),
        _observation(3, "20-50亿", 0.03), _observation(4, "50~100亿", 0.04),
        _observation(5, "0-5亿", 0.05), _observation(6, "10~20亿", 0.06),
    ]
    groups = {item["group_key"]: item for item in _analyze(rows)["strategies"][0]["groups"]}
    assert groups["large"]["sample_size"] == 2
    assert groups["medium"]["sample_size"] == 2
    assert groups["small"]["sample_size"] == 2
    categories = _analyze(rows)["strategies"][0]["categories"]
    assert [item["group_key"] for item in categories] == [
        "100亿以上", "50~100亿", "20~50亿", "10~20亿", "5~10亿", "0~5亿"]
    assert [item["sample_size"] for item in categories] == [2, 1, 1, 1, 0, 1]


def test_missing_weekly_excess_is_not_zero_in_group_statistics():
    group = _analyze([
        _observation(1, "100亿以上", None, weekly_return=0.01),
        _observation(2, "100亿以上", 0.02),
        _observation(3, "100亿以上", 0.04),
    ])["strategies"][0]["groups"][0]
    assert group["raw_observation_count"] == 3
    assert group["missing_weekly_excess_count"] == 1
    assert group["sample_size"] == 2
    assert group["weekly_excess_median"] == pytest.approx(0.03)


def test_group_below_minimum_keeps_facts_but_is_insufficient():
    group = _analyze([_observation(1, "100亿以上", 0.02)])["strategies"][0]["groups"][0]
    assert group["weekly_excess_median"] == 0.02
    assert group["status"] == "insufficient_sample"


def test_unknown_size_is_excluded_from_groups_and_counted_for_quality():
    strategy = _analyze([
        _observation(1, None, 0.10),
        _observation(2, "未知", 0.20),
        _observation(3, "100亿以上", 0.01),
        _observation(4, "100亿以上", 0.02),
    ])["strategies"][0]
    assert strategy["unknown_size_count"] == 2
    assert strategy["unknown_size_valid_excess_count"] == 2
    assert sum(group["raw_observation_count"] for group in strategy["groups"]) == 2


def test_effect_summary_selects_best_and_worst_qualified_groups():
    rows = [
        _observation(1, "100亿以上", -0.002), _observation(2, "100亿以上", 0.0),
        _observation(3, "20~50亿", 0.001), _observation(4, "50~100亿", 0.003),
        _observation(5, "0~5亿", 0.005), _observation(6, "5~10亿", 0.007),
    ]
    effect = _analyze(rows)["strategies"][0]["effect_summary"]
    assert effect["status"] == "meaningful"
    assert effect["best_group"] == "20亿以下"
    assert effect["worst_group"] == "百亿以上"
    assert effect["median_gap"] == pytest.approx(0.007)
    assert "0.70个百分点" in effect["headline"]


def test_effect_summary_is_neutral_when_gap_is_below_threshold():
    rows = [
        _observation(1, "100亿以上", 0.001), _observation(2, "100亿以上", 0.002),
        _observation(3, "20~50亿", 0.002), _observation(4, "50~100亿", 0.003),
    ]
    effect = _analyze(rows)["strategies"][0]["effect_summary"]
    assert effect["status"] == "neutral"
    assert effect["median_gap"] == pytest.approx(0.001)
    assert effect["headline"] == "不同管理规模之间未见明显差异"


def test_effect_summary_is_insufficient_with_only_one_qualified_group():
    rows = [
        _observation(1, "100亿以上", 0.001), _observation(2, "100亿以上", 0.002),
        _observation(3, "20~50亿", 0.01),
    ]
    effect = _analyze(rows)["strategies"][0]["effect_summary"]
    assert effect["status"] == "insufficient"
    assert effect["best_group"] is None
    assert effect["headline"] == "规模分组样本不足，暂不判断"
