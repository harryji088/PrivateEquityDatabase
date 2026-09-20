from datetime import date

import pytest

from analytics.alpha_heatmap import analyze_alpha_heatmap
from analytics.schemas import WeeklyObservation

STRATEGIES = {"index_500": {"label": "500指增", "benchmark_key": "CSI500"}}


def _observations(values_by_date):
    rows = []
    for day, values in values_by_date.items():
        for index, value in enumerate(values, start=1):
            rows.append(WeeklyObservation(
                as_of_date=date.fromisoformat(day), week_label=day,
                manager_id=index, manager_name=f"管理人{index}",
                strategy_key="index_500", strategy_label="500指增",
                weekly_return=value, weekly_excess=value, ytd_return=None,
                ytd_excess=None, ytd_excess_drawdown=None,
                source_row_id=f"{day}-{index}",
            ))
    return rows


def _analyze(values_by_date, minimum=2, weeks=12, threshold=0.0005):
    dates = list(values_by_date)
    return analyze_alpha_heatmap(
        _observations(values_by_date), dates, STRATEGIES, minimum, weeks, threshold)


def _history(result):
    return result["strategies"][0]["history"]


def test_recomputes_each_actual_week_cross_section_and_never_synthesizes_dates():
    result = _analyze({
        "2026-01-02": [0.01, 0.03],
        "2026-01-23": [-0.02, 0.00],
    })
    assert result["weeks"] == ["2026-01-02", "2026-01-23"]
    assert [_point["median_weekly_excess"] for _point in _history(result)] == pytest.approx([0.02, -0.01])


def test_limits_output_to_configured_latest_actual_weeks():
    values = {f"2026-01-{day:02d}": [0.01, 0.02] for day in (2, 9, 16, 23)}
    result = _analyze(values, weeks=2)
    assert result["weeks"] == ["2026-01-16", "2026-01-23"]


def test_calculates_quantiles_dispersion_and_strict_positive_ratio():
    point = _history(_analyze({"2026-01-02": [-0.01, 0.0, 0.01, 0.02]}))[0]
    assert point["p25"] == pytest.approx(-0.0025)
    assert point["p75"] == pytest.approx(0.0125)
    assert point["dispersion_p75_p25"] == pytest.approx(0.015)
    assert point["positive_excess_ratio"] == 0.5


def test_missing_excess_is_not_zero_and_quality_counts_are_preserved():
    point = _history(_analyze({"2026-01-02": [None, 0.01, 0.03]}))[0]
    assert point["raw_observation_count"] == 3
    assert point["missing_weekly_excess_count"] == 1
    assert point["sample_size"] == 2
    assert point["median_weekly_excess"] == pytest.approx(0.02)


def test_sample_below_minimum_is_insufficient_even_when_median_exists():
    point = _history(_analyze({"2026-01-02": [0.02]}, minimum=2))[0]
    assert point["median_weekly_excess"] == 0.02
    assert point["status"] == "insufficient_sample"


def test_threshold_boundaries_are_neutral_and_strictly_outside_are_directional():
    result = _analyze({
        "2026-01-02": [0.0005, 0.0005],
        "2026-01-09": [-0.0005, -0.0005],
        "2026-01-16": [0.0006, 0.0006],
        "2026-01-23": [-0.0006, -0.0006],
    })
    assert [point["status"] for point in _history(result)] == [
        "neutral", "neutral", "positive", "negative"]


def test_stability_counts_direction_weeks_and_immediate_switches():
    result = _analyze({
        "2026-01-02": [0.01, 0.01],
        "2026-01-09": [-0.01, -0.01],
        "2026-01-16": [0.02, 0.02],
    })
    stability = result["strategies"][0]["stability"]
    assert stability["switch_count"] == 2
    assert stability["positive_week_count"] == 2
    assert stability["negative_week_count"] == 1
    assert stability["current_positive_streak"] == 1


def test_neutral_breaks_streak_and_prevents_nonadjacent_switch():
    result = _analyze({
        "2026-01-02": [0.01, 0.01],
        "2026-01-09": [0.0, 0.0],
        "2026-01-16": [-0.01, -0.01],
    })
    stability = result["strategies"][0]["stability"]
    assert stability["switch_count"] == 0
    assert stability["current_negative_streak"] == 1
    assert stability["neutral_week_count"] == 1


def test_insufficient_sample_breaks_streak_and_is_not_an_available_week():
    result = _analyze({
        "2026-01-02": [0.01, 0.01],
        "2026-01-09": [0.01],
        "2026-01-16": [0.01, 0.01],
    })
    stability = result["strategies"][0]["stability"]
    assert stability["current_positive_streak"] == 1
    assert stability["available_week_count"] == 2
    assert stability["insufficient_week_count"] == 1


def test_three_adjacent_positive_weeks_take_sustained_priority():
    result = _analyze({
        "2026-01-02": [0.001, 0.001],
        "2026-01-09": [0.002, 0.002],
        "2026-01-16": [0.003, 0.003],
    })
    assert result["strategies"][0]["trend"]["state"] == "sustained_positive"


def test_three_adjacent_negative_weeks_are_sustained_negative():
    result = _analyze({
        "2026-01-02": [-0.001, -0.001],
        "2026-01-09": [-0.002, -0.002],
        "2026-01-16": [-0.003, -0.003],
    })
    assert result["strategies"][0]["trend"]["state"] == "sustained_negative"


def test_improving_requires_latest_above_previous_and_recent_four_week_median():
    result = _analyze({
        "2026-01-02": [-0.01, -0.01],
        "2026-01-09": [0.002, 0.002],
        "2026-01-16": [0.004, 0.004],
    })
    assert result["strategies"][0]["trend"]["state"] == "improving"


def test_deteriorating_requires_latest_below_previous_and_recent_four_week_median():
    result = _analyze({
        "2026-01-02": [0.01, 0.01],
        "2026-01-09": [-0.002, -0.002],
        "2026-01-16": [-0.004, -0.004],
    })
    assert result["strategies"][0]["trend"]["state"] == "deteriorating"


def test_summary_is_structured_and_headline_is_precomputed():
    result = _analyze({"2026-01-02": [0.01, 0.02]})
    summary = result["summary"]
    assert summary["strongest_strategy"]["strategy_key"] == "index_500"
    assert summary["weakest_strategy"]["strategy_key"] == "index_500"
    assert "500指增" in summary["headline"]


def test_all_insufficient_samples_produce_no_strongest_or_weakest():
    result = _analyze({"2026-01-02": [0.01]}, minimum=2)
    assert result["summary"]["strongest_strategy"] is None
    assert result["summary"]["weakest_strategy"] is None
    assert "样本不足" in result["summary"]["headline"]
