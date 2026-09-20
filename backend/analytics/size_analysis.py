"""Current-week manager size-group analysis for index-enhancement strategies."""

from __future__ import annotations

from typing import Any

from analytics.metrics import descriptive_stats, positive_ratio, valid_values
from analytics.schemas import WeeklyObservation

CANONICAL_SIZE_CATEGORIES = (
    "100亿以上", "50~100亿", "20~50亿", "10~20亿", "5~10亿", "0~5亿",
)
UNKNOWN_SIZE_CATEGORY = "未知"


def normalize_size_category(value: str | None) -> str:
    """Normalize known labels without estimating a manager's size."""
    if value is None:
        return UNKNOWN_SIZE_CATEGORY
    normalized = str(value).strip().replace("～", "~").replace("-", "~")
    if normalized in CANONICAL_SIZE_CATEGORIES:
        return normalized
    return UNKNOWN_SIZE_CATEGORY


def analyze_size_groups(
        observations: list[WeeklyObservation], as_of_date: str,
        strategies: dict[str, dict[str, Any]],
        size_config: dict[str, Any]) -> dict[str, Any]:
    """Compute strategy-by-size-group facts from the current weekly cross-section."""
    current = [item for item in observations if item.as_of_date.isoformat() == as_of_date]
    configured_groups = [
        {
            "group_key": key,
            "group_label": details["label"],
            "categories": list(details["categories"]),
        }
        for key, details in size_config["groups"].items()
    ]
    category_to_group = {
        category: group["group_key"]
        for group in configured_groups
        for category in group["categories"]
    }
    minimum = size_config["min_size_group_sample_size"]
    minimum_gap = size_config["size_effect_min_gap"]
    strategy_facts = []
    for strategy_key, strategy_config in strategies.items():
        strategy_rows = [item for item in current if item.strategy_key == strategy_key]
        unknown_rows = [
            item for item in strategy_rows
            if category_to_group.get(normalize_size_category(item.size_category)) is None
        ]
        groups = []
        for group in configured_groups:
            rows = [
                item for item in strategy_rows
                if category_to_group.get(normalize_size_category(item.size_category))
                == group["group_key"]
            ]
            groups.append(_group_facts(group, rows, minimum))
        categories = []
        for category in CANONICAL_SIZE_CATEGORIES:
            rows = [
                item for item in strategy_rows
                if normalize_size_category(item.size_category) == category
            ]
            categories.append(_group_facts({
                "group_key": category,
                "group_label": category,
                "categories": [category],
            }, rows, minimum))
        effect = _effect_summary(
            strategy_key, strategy_config["label"], groups, minimum_gap)
        strategy_facts.append({
            "strategy_key": strategy_key,
            "strategy_label": strategy_config["label"],
            "groups": groups,
            "categories": categories,
            "effect_summary": effect,
            "unknown_size_count": len(unknown_rows),
            "unknown_size_valid_excess_count": len(valid_values(
                item.weekly_excess for item in unknown_rows)),
        })

    meaningful = [
        {
            "strategy_key": item["strategy_key"],
            "strategy_label": item["strategy_label"],
            "median_gap": item["effect_summary"]["median_gap"],
            "headline": item["effect_summary"]["headline"],
        }
        for item in strategy_facts
        if item["effect_summary"]["status"] == "meaningful"
    ]
    return {
        "enabled": size_config["enabled"],
        "as_of_date": as_of_date,
        "methodology": {
            "source": "weekly_performances.size_category",
            "grain": "strategy_current_week_size_group_cross_section",
            "min_size_group_sample_size": minimum,
            "size_effect_min_gap": minimum_gap,
            "unknown_category_policy": "excluded_from_groups_and_counted_in_data_quality",
        },
        "groups": configured_groups,
        "category_order": list(CANONICAL_SIZE_CATEGORIES),
        "strategies": strategy_facts,
        "summary": {
            "meaningful_effect_count": len(meaningful),
            "meaningful_effects": meaningful,
            "headline": (
                max(meaningful, key=lambda item: item["median_gap"])["headline"]
                if meaningful else ""),
        },
    }


def _group_facts(
        group: dict[str, Any], rows: list[WeeklyObservation], minimum: int) -> dict[str, Any]:
    excess_values = valid_values(item.weekly_excess for item in rows)
    return_values = valid_values(item.weekly_return for item in rows)
    excess_stats = descriptive_stats(excess_values)
    p25 = excess_stats["p25"]
    p75 = excess_stats["p75"]
    sample_size = len(excess_values)
    return {
        "group_key": group["group_key"],
        "group_label": group["group_label"],
        "categories": list(group["categories"]),
        "raw_observation_count": len(rows),
        "missing_weekly_excess_count": len(rows) - sample_size,
        "sample_size": sample_size,
        "weekly_return_sample_size": len(return_values),
        "weekly_return_median": descriptive_stats(return_values)["median"],
        "weekly_excess_median": excess_stats["median"],
        "weekly_excess_p25": p25,
        "weekly_excess_p75": p75,
        "weekly_excess_dispersion": (
            p75 - p25 if p25 is not None and p75 is not None else None),
        "positive_excess_ratio": positive_ratio(excess_values),
        "status": "ok" if sample_size >= minimum else "insufficient_sample",
    }


def _effect_summary(
        strategy_key: str, strategy_label: str, groups: list[dict[str, Any]],
        minimum_gap: float) -> dict[str, Any]:
    eligible = [
        group for group in groups
        if group["status"] == "ok" and group["weekly_excess_median"] is not None
    ]
    if len(eligible) < 2:
        return {
            "strategy_key": strategy_key,
            "status": "insufficient",
            "best_group": None,
            "best_group_key": None,
            "worst_group": None,
            "worst_group_key": None,
            "median_gap": None,
            "headline": "规模分组样本不足，暂不判断",
        }
    best = max(eligible, key=lambda item: item["weekly_excess_median"])
    worst = min(eligible, key=lambda item: item["weekly_excess_median"])
    gap = best["weekly_excess_median"] - worst["weekly_excess_median"]
    if gap >= minimum_gap:
        status = "meaningful"
        headline = (
            "{}本周{}管理人超额中位数较{}高{:.2f}个百分点，规模组之间存在较明显分化。"
            .format(strategy_label, best["group_label"], worst["group_label"], gap * 100)
        )
    else:
        status = "neutral"
        headline = "不同管理规模之间未见明显差异"
    return {
        "strategy_key": strategy_key,
        "status": status,
        "best_group": best["group_label"],
        "best_group_key": best["group_key"],
        "worst_group": worst["group_label"],
        "worst_group_key": worst["group_key"],
        "median_gap": gap,
        "headline": headline,
    }
