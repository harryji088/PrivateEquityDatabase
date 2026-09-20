"""Assembly, validation, and atomic persistence of report facts."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from analytics import ANALYTICS_VERSION
from analytics.schemas import AnalyticsError


def build_facts(
        database_path: Path, benchmark_path: Path, style_path: Path, as_of_date: str,
        previous_as_of_date: str | None, report_config: dict[str, Any],
        benchmark_analysis: dict[str, Any], style_analysis: dict[str, Any],
        universe: dict[str, Any], focus_managers: list[dict[str, Any]],
        focus_warnings: list[str], alerts: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a single renderer-independent, JSON-safe source of report truth."""
    benchmark_returns = {
        item["benchmark_key"]: item["weekly_return"]
        for item in benchmark_analysis["benchmarks"]
    }
    for summary in universe["strategy_summary"]:
        summary["benchmark_return"] = benchmark_returns.get(summary["benchmark_key"])

    _attach_alerts(focus_managers, alerts)
    raw_count = sum(item["data_quality"]["raw_observation_count"]
                    for item in universe["strategy_summary"])
    valid_count = sum(item["sample_size"] for item in universe["strategy_summary"])
    missing_strategies = [
        item["strategy_key"] for item in universe["strategy_summary"]
        if item["data_quality"]["raw_observation_count"] == 0
    ]
    insufficient_samples = [
        item["strategy_key"] for item in universe["strategy_summary"]
        if item["data_quality"]["status"] == "insufficient_sample"
    ]
    warnings = (list(benchmark_analysis["warnings"]) + list(style_analysis["warnings"]) +
                list(focus_warnings))
    if missing_strategies:
        warnings.append("以下策略没有当前有效观测：{}".format(", ".join(missing_strategies)))
    facts = {
        "schema_version": "1.0",
        "analytics_version": ANALYTICS_VERSION,
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "as_of_date": as_of_date,
        "previous_as_of_date": previous_as_of_date,
        "data_sources": {
            "database": str(database_path.resolve()),
            "benchmark_nav": str(benchmark_path.resolve()),
            "style_index_nav": str(style_path.resolve()),
            "database_access": "sqlite_read_only",
        },
        "methodology": {
            "entity_grain": "manager_strategy",
            "return_unit": "decimal",
            "weekly_return_source": "weekly_performances.weekly_return",
            "excess_source": "weekly_performances.weekly_excess",
            "excess_definition": "official_database_weekly_excess_by_strategy",
            "rolling_excess_aggregation": "simple_sum_of_weekly_excess",
            "benchmark_return_definition": "nav(end_on_or_before_as_of) / nav(start_on_or_before_previous_as_of) - 1",
            "style_return_definition": "style_spread = long_leg_cumulative_return - short_leg_cumulative_return",
            "style_data_source": "locally_cached_csindex_daily_price_indices",
            "style_max_staleness_days": report_config["style"]["max_staleness_days"],
            "style_neutral_spread_threshold": report_config["style"]["neutral_spread_threshold"],
            "style_category_conclusion": "all_configured_proxies_must_be_available_and_aligned",
            "quantile_method": "linear_position_q_times_n_minus_1",
            "standard_deviation": "population",
            "min_sample_size": report_config["report"]["min_sample_size"],
        },
        "data_quality": {
            "status": "warning" if warnings or missing_strategies or insufficient_samples else "ok",
            "warnings": warnings,
            "missing_strategies": missing_strategies,
            "insufficient_samples": insufficient_samples,
            "sample_coverage": valid_count / raw_count if raw_count else 0.0,
            "valid_weekly_excess_count": valid_count,
            "raw_current_observation_count": raw_count,
        },
        "market": dict(benchmark_analysis, style=style_analysis),
        "strategy_summary": universe["strategy_summary"],
        "strategy_trend": universe["strategy_trend"],
        "focus_managers": focus_managers,
        "alerts": alerts,
    }
    validate_facts(facts)
    return facts


def validate_facts(facts: dict[str, Any]) -> None:
    """Perform focused schema checks before any report artifact is written."""
    required = (
        "schema_version", "analytics_version", "generated_at", "as_of_date",
        "data_sources", "methodology", "data_quality", "market", "strategy_summary",
        "strategy_trend", "focus_managers", "alerts",
    )
    missing = [key for key in required if key not in facts]
    if missing:
        raise AnalyticsError("Facts missing required keys: {}".format(", ".join(missing)))
    if facts["schema_version"] != "1.0":
        raise AnalyticsError("Unsupported facts schema version")
    if facts["methodology"]["return_unit"] != "decimal":
        raise AnalyticsError("Facts return unit must be decimal")
    try:
        datetime.strptime(facts["as_of_date"], "%Y-%m-%d")
        if facts["previous_as_of_date"]:
            datetime.strptime(facts["previous_as_of_date"], "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise AnalyticsError("Facts contain invalid report date") from exc
    for summary in facts["strategy_summary"]:
        if summary["as_of_date"] != facts["as_of_date"]:
            raise AnalyticsError("Strategy facts do not share report as_of_date")
        if summary["sample_size"] < 0:
            raise AnalyticsError("Strategy sample size cannot be negative")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write a complete JSON file or leave no partial artifact behind."""
    _write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_text_atomic(path: Path, content: str) -> None:
    """Write a complete text file or leave no partial artifact behind."""
    _write_text_atomic(path, content)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _attach_alerts(cards: list[dict[str, Any]], alerts: list[dict[str, Any]]) -> None:
    by_key = {}
    for item in alerts:
        by_key.setdefault((item["manager_name"], item.get("strategy_key")), []).append(item)
    for card in cards:
        matches = by_key.get((card["manager_name"], card.get("strategy_key")))
        if matches:
            card["alerts"] = matches
