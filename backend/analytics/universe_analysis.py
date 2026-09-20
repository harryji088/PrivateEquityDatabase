"""Cross-sectional manager-by-strategy analysis for the weekly report."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from analytics.metrics import (
    consecutive_sign_count,
    descriptive_stats,
    positive_ratio,
    quantile,
    rank_desc,
    trailing_complete_values,
)
from analytics.schemas import WeeklyObservation


def _observation_dict(item: WeeklyObservation) -> dict[str, Any]:
    return {
        "manager_id": item.manager_id,
        "manager_name": item.manager_name,
        "strategy_key": item.strategy_key,
        "strategy_label": item.strategy_label,
        "weekly_return": item.weekly_return,
        "weekly_excess": item.weekly_excess,
        "ytd_return": item.ytd_return,
        "ytd_excess": item.ytd_excess,
        "ytd_excess_drawdown": item.ytd_excess_drawdown,
        "source_row_id": item.source_row_id,
    }


def _rank_at_date(
        observations: Iterable[WeeklyObservation], target_date: str | None) -> dict[tuple[int, str], dict[str, Any]]:
    if not target_date:
        return {}
    by_strategy = defaultdict(list)
    for item in observations:
        if item.as_of_date.isoformat() == target_date:
            by_strategy[item.strategy_key].append(_observation_dict(item))
    result = {}
    for strategy_key, records in by_strategy.items():
        for item in rank_desc(records, "weekly_excess", "manager_name"):
            result[(item["manager_id"], strategy_key)] = item
    return result


def _history_maps(observations: Iterable[WeeklyObservation]) -> dict[tuple[int, str], dict[str, WeeklyObservation]]:
    histories = defaultdict(dict)
    for item in observations:
        histories[(item.manager_id, item.strategy_key)][item.as_of_date.isoformat()] = item
    return histories


def _rolling_value(
        history: dict[str, WeeklyObservation], report_dates: list[str], as_of_date: str,
        window: int) -> float | None:
    values_by_date = {item_date: item.weekly_excess for item_date, item in history.items()}
    values = trailing_complete_values(values_by_date, report_dates, as_of_date, window)
    return sum(values) if values is not None else None


def _trailing_excesses(
        history: dict[str, WeeklyObservation], report_dates: list[str], as_of_date: str) -> list[float | None]:
    end = report_dates.index(as_of_date) + 1
    return [history.get(item_date).weekly_excess if item_date in history else None
            for item_date in report_dates[:end]]


def analyze_universe(
        observations: list[WeeklyObservation], report_dates: list[str], as_of_date: str,
        previous_as_of_date: str | None, strategies: dict[str, Any], min_sample_size: int,
        recent_windows: list[int]) -> dict[str, Any]:
    """Produce strategy summaries and ranked manager-strategy records."""
    histories = _history_maps(observations)
    previous_ranks = _rank_at_date(observations, previous_as_of_date)
    summaries = []
    trends = []
    all_current = [item for item in observations if item.as_of_date.isoformat() == as_of_date]
    previous_current = [item for item in observations
                        if item.as_of_date.isoformat() == previous_as_of_date]

    for strategy_key, strategy_config in strategies.items():
        current_rows = [item for item in all_current if item.strategy_key == strategy_key]
        previous_rows = [item for item in previous_current if item.strategy_key == strategy_key]
        ranked = rank_desc(
            [_observation_dict(item) for item in current_rows], "weekly_excess", "manager_name")
        for record in ranked:
            history = histories[(record["manager_id"], strategy_key)]
            previous = previous_ranks.get((record["manager_id"], strategy_key))
            record["previous_rank"] = previous["rank"] if previous else None
            record["previous_peer_percentile"] = previous["peer_percentile"] if previous else None
            record["rank_change"] = (
                previous["rank"] - record["rank"] if previous else None)
            record["peer_percentile_change"] = (
                record["peer_percentile"] - previous["peer_percentile"]
                if previous and record["peer_percentile"] is not None
                and previous["peer_percentile"] is not None else None)
            record["previous_excess"] = previous["weekly_excess"] if previous else None
            record["rolling"] = {}
            for window in recent_windows:
                record["rolling"][f"weeks_{window}"] = {
                    "cumulative_excess": _rolling_value(history, report_dates, as_of_date, window),
                }
            trailing = _trailing_excesses(history, report_dates, as_of_date)
            record["consecutive_positive_weeks"] = consecutive_sign_count(trailing, positive=True)
            record["consecutive_negative_weeks"] = consecutive_sign_count(trailing, positive=False)

        excess_stats = descriptive_stats([item.weekly_excess for item in current_rows])
        excess_stats["p10"] = quantile([item.weekly_excess for item in current_rows], 0.10)
        excess_stats["p90"] = quantile([item.weekly_excess for item in current_rows], 0.90)
        excess_stats["dispersion_p75_p25"] = (
            excess_stats["p75"] - excess_stats["p25"]
            if excess_stats["p75"] is not None and excess_stats["p25"] is not None else None)
        product_stats = descriptive_stats([item.weekly_return for item in current_rows])
        current_sample = len(ranked)
        raw_sample = len(current_rows)

        rolling_summary = {}
        for window in recent_windows:
            key = f"weeks_{window}"
            values = [item["rolling"][key]["cumulative_excess"] for item in ranked]
            rolling_stats = descriptive_stats(values)
            rolling_summary[key] = {
                "sample_size": sum(value is not None for value in values),
                "median_excess": rolling_stats["median"],
                "positive_ratio": positive_ratio(values),
                "p10": quantile(values, 0.10),
                "p90": quantile(values, 0.90),
            }

        previous_excess_stats = descriptive_stats(
            [item.weekly_excess for item in previous_rows])
        previous_dispersion = (
            previous_excess_stats["p75"] - previous_excess_stats["p25"]
            if previous_excess_stats["p75"] is not None and previous_excess_stats["p25"] is not None else None)
        comparison = {
            "median_excess_change": _difference(
                excess_stats["median"], previous_excess_stats["median"]),
            "dispersion_change": _difference(
                excess_stats["dispersion_p75_p25"], previous_dispersion),
            "positive_ratio_change": _difference(
                positive_ratio([item.weekly_excess for item in current_rows]),
                positive_ratio([item.weekly_excess for item in previous_rows])),
        }
        data_quality = {
            "status": "ok" if current_sample >= min_sample_size else "insufficient_sample",
            "raw_observation_count": raw_sample,
            "missing_weekly_excess_count": raw_sample - current_sample,
            "field_coverage": current_sample / raw_sample if raw_sample else 0.0,
        }
        summary = {
            "strategy_key": strategy_key,
            "strategy_label": strategy_config["label"],
            "benchmark_key": strategy_config["benchmark_key"],
            "as_of_date": as_of_date,
            "sample_size": current_sample,
            "manager_strategy_return": product_stats,
            "excess_return": excess_stats,
            "positive_excess_ratio": positive_ratio([item.weekly_excess for item in current_rows]),
            "ranked_managers": ranked,
            "rolling": rolling_summary,
            "comparison": comparison,
            "data_quality": data_quality,
        }
        summaries.append(summary)
        trends.append({
            "strategy_key": strategy_key,
            "strategy_label": strategy_config["label"],
            "rolling": rolling_summary,
            "comparison": comparison,
            "data_quality": data_quality,
        })

    return {"strategy_summary": summaries, "strategy_trend": trends, "histories": histories}


def _difference(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous
