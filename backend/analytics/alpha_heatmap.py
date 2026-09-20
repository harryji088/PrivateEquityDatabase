"""Weekly cross-sectional Alpha heatmap facts.

Each cell is recomputed from all manager-strategy observations for one actual
report date.  This deliberately differs from the per-manager rolling sums used
elsewhere in the weekly report.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from analytics.metrics import descriptive_stats, positive_ratio, quantile, valid_values
from analytics.schemas import WeeklyObservation

EFFECTIVE_DIRECTIONS = {"positive", "negative"}
TREND_LABELS = {
    "sustained_positive": "Alpha环境连续偏强",
    "sustained_negative": "Alpha环境连续偏弱",
    "improving": "近期改善",
    "deteriorating": "近期转弱",
    "mixed": "近期波动",
}


def analyze_alpha_heatmap(
        observations: Iterable[WeeklyObservation], report_dates: list[str],
        strategies: dict[str, dict[str, Any]], min_sample_size: int,
        weeks: int, neutral_excess_threshold: float) -> dict[str, Any]:
    """Build renderer-ready cross-sectional facts for the latest actual weeks."""
    selected_dates = list(report_dates[-weeks:])
    rows = list(observations)
    strategy_facts = []
    for strategy_key, details in strategies.items():
        history = [
            _weekly_cross_section(
                rows, strategy_key, report_date, min_sample_size,
                neutral_excess_threshold)
            for report_date in selected_dates
        ]
        stability = _stability(history)
        trend = _trend(history, stability)
        strategy_facts.append({
            "strategy_key": strategy_key,
            "strategy_label": details["label"],
            "history": history,
            "stability": stability,
            "trend": trend,
        })

    summary = _summary(strategy_facts)
    return {
        "weeks": selected_dates,
        "strategies": strategy_facts,
        "summary": summary,
    }


def _weekly_cross_section(
        observations: list[WeeklyObservation], strategy_key: str,
        report_date: str, min_sample_size: int,
        neutral_excess_threshold: float) -> dict[str, Any]:
    matching = [
        item for item in observations
        if item.strategy_key == strategy_key and item.as_of_date.isoformat() == report_date
    ]
    values = valid_values(item.weekly_excess for item in matching)
    stats = descriptive_stats(values)
    sample_size = len(values)
    median = stats["median"]
    if sample_size < min_sample_size:
        status = "insufficient_sample"
    elif median is not None and median > neutral_excess_threshold:
        status = "positive"
    elif median is not None and median < -neutral_excess_threshold:
        status = "negative"
    else:
        status = "neutral"
    p25 = stats["p25"]
    p75 = stats["p75"]
    return {
        "as_of_date": report_date,
        "raw_observation_count": len(matching),
        "missing_weekly_excess_count": len(matching) - sample_size,
        "sample_size": sample_size,
        "median_weekly_excess": median,
        "positive_excess_ratio": positive_ratio(values),
        "p25": p25,
        "p75": p75,
        "dispersion_p75_p25": p75 - p25 if p25 is not None and p75 is not None else None,
        "status": status,
    }


def _stability(history: list[dict[str, Any]]) -> dict[str, int]:
    statuses = [point["status"] for point in history]
    current_positive_streak = _trailing_status_count(statuses, "positive")
    current_negative_streak = _trailing_status_count(statuses, "negative")
    switch_count = sum(
        previous in EFFECTIVE_DIRECTIONS and current in EFFECTIVE_DIRECTIONS
        and previous != current
        for previous, current in zip(statuses, statuses[1:])
    )
    return {
        "current_positive_streak": current_positive_streak,
        "current_negative_streak": current_negative_streak,
        "switch_count": switch_count,
        "positive_week_count": statuses.count("positive"),
        "negative_week_count": statuses.count("negative"),
        "neutral_week_count": statuses.count("neutral"),
        "available_week_count": sum(status != "insufficient_sample" for status in statuses),
        "insufficient_week_count": statuses.count("insufficient_sample"),
    }


def _trailing_status_count(statuses: list[str], target: str) -> int:
    count = 0
    for status in reversed(statuses):
        if status != target:
            break
        count += 1
    return count


def _trend(history: list[dict[str, Any]], stability: dict[str, int]) -> dict[str, str]:
    if stability["current_positive_streak"] >= 3:
        state = "sustained_positive"
    elif stability["current_negative_streak"] >= 3:
        state = "sustained_negative"
    elif _has_directional_change(history, improving=True):
        state = "improving"
    elif _has_directional_change(history, improving=False):
        state = "deteriorating"
    else:
        state = "mixed"
    return {"state": state, "label": TREND_LABELS[state]}


def _has_directional_change(history: list[dict[str, Any]], improving: bool) -> bool:
    if len(history) < 2:
        return False
    latest, previous = history[-1], history[-2]
    if latest["status"] == "insufficient_sample" or previous["status"] == "insufficient_sample":
        return False
    latest_value = latest["median_weekly_excess"]
    previous_value = previous["median_weekly_excess"]
    recent_values = valid_values(
        point["median_weekly_excess"]
        for point in history[-4:]
        if point["status"] != "insufficient_sample"
    )
    recent_median = quantile(recent_values, 0.5)
    if latest_value is None or previous_value is None or recent_median is None:
        return False
    if improving:
        return latest_value > previous_value and latest_value > recent_median
    return latest_value < previous_value and latest_value < recent_median


def _summary(strategies: list[dict[str, Any]]) -> dict[str, Any]:
    latest = []
    grouped = {key: [] for key in TREND_LABELS}
    for strategy in strategies:
        trend_state = strategy["trend"]["state"]
        grouped[trend_state].append(_strategy_reference(strategy))
        point = strategy["history"][-1] if strategy["history"] else None
        if point and point["status"] != "insufficient_sample" and point["median_weekly_excess"] is not None:
            latest.append((float(point["median_weekly_excess"]), strategy))

    strongest = _latest_reference(max(latest, default=None, key=lambda item: item[0]))
    weakest = _latest_reference(min(latest, default=None, key=lambda item: item[0]))
    headline = _headline(strongest, weakest, grouped)
    return {
        "strongest_strategy": strongest,
        "weakest_strategy": weakest,
        "sustained_positive": grouped["sustained_positive"],
        "sustained_negative": grouped["sustained_negative"],
        "improving": grouped["improving"],
        "deteriorating": grouped["deteriorating"],
        "mixed": grouped["mixed"],
        "headline": headline,
    }


def _strategy_reference(strategy: dict[str, Any]) -> dict[str, str]:
    return {
        "strategy_key": strategy["strategy_key"],
        "strategy_label": strategy["strategy_label"],
    }


def _latest_reference(item: tuple[float, dict[str, Any]] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    value, strategy = item
    result = _strategy_reference(strategy)
    result["median_weekly_excess"] = value
    return result


def _headline(
        strongest: dict[str, Any] | None, weakest: dict[str, Any] | None,
        grouped: dict[str, list[dict[str, str]]]) -> str:
    if strongest is None or weakest is None:
        return "本周有效样本不足，暂不判断指增 Alpha 强弱。"
    parts = [
        "本周{}横截面 Alpha 最强，{}最弱".format(
            strongest["strategy_label"], weakest["strategy_label"])
    ]
    if grouped["sustained_positive"]:
        parts.append("{}连续正向".format("、".join(
            item["strategy_label"] for item in grouped["sustained_positive"])))
    if grouped["sustained_negative"]:
        parts.append("{}连续负向".format("、".join(
            item["strategy_label"] for item in grouped["sustained_negative"])))
    if grouped["improving"]:
        parts.append("{}边际改善".format("、".join(
            item["strategy_label"] for item in grouped["improving"])))
    if grouped["deteriorating"]:
        parts.append("{}边际走弱".format("、".join(
            item["strategy_label"] for item in grouped["deteriorating"])))
    return "；".join(parts) + "。"
