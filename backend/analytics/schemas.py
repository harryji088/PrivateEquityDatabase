"""Stable internal records and configuration validation for weekly reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


class AnalyticsError(ValueError):
    """Raised when an input cannot produce a trustworthy report."""


@dataclass(frozen=True)
class WeeklyObservation:
    """One database record, expressed in the report's stable vocabulary."""

    as_of_date: date
    week_label: str
    manager_id: int
    manager_name: str
    strategy_key: str
    strategy_label: str
    weekly_return: float | None
    weekly_excess: float | None
    ytd_return: float | None
    ytd_excess: float | None
    ytd_excess_drawdown: float | None
    source_row_id: str
    size_category: str | None = None


DEFAULT_STRATEGY_LABELS = {
    "index_300": "300指增",
    "index_500": "500指增",
    "index_1000": "1000指增",
    "index_2000": "2000指增",
    "index_a500": "A500指增",
}


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnalyticsError(f"{label} must be a mapping")
    return value


def _require_number(value: Any, label: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalyticsError(f"{label} must be numeric")
    result = float(value)
    if minimum is not None and result < minimum:
        raise AnalyticsError(f"{label} must be >= {minimum}")
    return result


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping with a useful, path-specific error."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            content = yaml.safe_load(handle)
    except OSError as exc:
        raise AnalyticsError(f"Cannot read config {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise AnalyticsError(f"Invalid YAML in {path}: {exc}") from exc
    return _require_mapping(content or {}, str(path))


def load_report_config(path: Path) -> dict[str, Any]:
    """Validate only the configuration that V1 actually consumes."""
    config = load_yaml(path)
    if config.get("version") != 1:
        raise AnalyticsError(f"{path}: version must be 1")

    report = _require_mapping(config.get("report"), "report")
    windows = report.get("recent_windows")
    if not isinstance(windows, list) or not windows:
        raise AnalyticsError("report.recent_windows must be a non-empty list")
    report["recent_windows"] = [int(_require_number(
        value, "report.recent_windows", 1)) for value in windows]
    if 4 not in report["recent_windows"] or 12 not in report["recent_windows"]:
        raise AnalyticsError("report.recent_windows must include 4 and 12")
    report["min_sample_size"] = int(_require_number(
        report.get("min_sample_size"), "report.min_sample_size", 1))
    if report.get("timezone") != "Asia/Shanghai":
        raise AnalyticsError("report.timezone must be Asia/Shanghai in V1")

    alpha_heatmap = _require_mapping(config.get("alpha_heatmap"), "alpha_heatmap")
    if not isinstance(alpha_heatmap.get("enabled"), bool):
        raise AnalyticsError("alpha_heatmap.enabled must be boolean")
    alpha_heatmap["weeks"] = int(_require_number(
        alpha_heatmap.get("weeks"), "alpha_heatmap.weeks", 1))
    alpha_heatmap["neutral_excess_threshold"] = _require_number(
        alpha_heatmap.get("neutral_excess_threshold"),
        "alpha_heatmap.neutral_excess_threshold", 0)
    if alpha_heatmap["neutral_excess_threshold"] >= 1:
        raise AnalyticsError("alpha_heatmap.neutral_excess_threshold must be < 1")

    size_groups = _require_mapping(config.get("size_groups"), "size_groups")
    if not isinstance(size_groups.get("enabled"), bool):
        raise AnalyticsError("size_groups.enabled must be boolean")
    size_groups["min_size_group_sample_size"] = int(_require_number(
        size_groups.get("min_size_group_sample_size"),
        "size_groups.min_size_group_sample_size", 1))
    size_groups["size_effect_min_gap"] = _require_number(
        size_groups.get("size_effect_min_gap"), "size_groups.size_effect_min_gap", 0)
    if size_groups["size_effect_min_gap"] >= 1:
        raise AnalyticsError("size_groups.size_effect_min_gap must be < 1")
    group_config = _require_mapping(size_groups.get("groups"), "size_groups.groups")
    if not group_config:
        raise AnalyticsError("size_groups.groups must not be empty")
    known_categories = {
        "100亿以上", "50~100亿", "20~50亿", "10~20亿", "5~10亿", "0~5亿",
    }
    assigned_categories = []
    for group_key, details in group_config.items():
        details = _require_mapping(details, f"size_groups.groups.{group_key}")
        if not isinstance(details.get("label"), str) or not details["label"]:
            raise AnalyticsError(f"size_groups.groups.{group_key}.label must be a string")
        categories = details.get("categories")
        if not isinstance(categories, list) or not categories:
            raise AnalyticsError(
                f"size_groups.groups.{group_key}.categories must be a non-empty list")
        if not all(isinstance(item, str) and item in known_categories for item in categories):
            raise AnalyticsError(
                f"size_groups.groups.{group_key}.categories contains an unknown category")
        assigned_categories.extend(categories)
    if len(assigned_categories) != len(set(assigned_categories)):
        raise AnalyticsError("size_groups categories must not overlap")
    if set(assigned_categories) != known_categories:
        raise AnalyticsError("size_groups must assign every canonical size category exactly once")

    benchmarks = _require_mapping(config.get("benchmarks"), "benchmarks")
    for benchmark_key, details in benchmarks.items():
        details = _require_mapping(details, f"benchmarks.{benchmark_key}")
        if not isinstance(details.get("source_key"), str) or not details["source_key"]:
            raise AnalyticsError(f"benchmarks.{benchmark_key}.source_key must be a string")
        if not isinstance(details.get("label"), str) or not details["label"]:
            details["label"] = details["source_key"]

    style = _require_mapping(config.get("style"), "style")
    if not isinstance(style.get("data_path"), str) or not style["data_path"]:
        raise AnalyticsError("style.data_path must be a non-empty string")
    style["heatmap_weeks"] = int(_require_number(
        style.get("heatmap_weeks"), "style.heatmap_weeks", 1))
    style["max_staleness_days"] = int(_require_number(
        style.get("max_staleness_days"), "style.max_staleness_days", 0))
    style["neutral_spread_threshold"] = _require_number(
        style.get("neutral_spread_threshold"), "style.neutral_spread_threshold", 0)
    if style["neutral_spread_threshold"] >= 1:
        raise AnalyticsError("style.neutral_spread_threshold must be < 1")
    style_indices = _require_mapping(style.get("indices"), "style.indices")
    if not style_indices:
        raise AnalyticsError("style.indices must not be empty")
    for style_key, details in style_indices.items():
        details = _require_mapping(details, f"style.indices.{style_key}")
        for field in ("label", "source_key", "wind_code", "csindex_code"):
            if not isinstance(details.get(field), str) or not details[field]:
                raise AnalyticsError(f"style.indices.{style_key}.{field} must be a non-empty string")
        query_alias = details.get("query_alias")
        if query_alias is not None and (not isinstance(query_alias, str) or not query_alias):
            raise AnalyticsError(f"style.indices.{style_key}.query_alias must be a non-empty string")

    proxies = style.get("proxies")
    if not isinstance(proxies, list) or not proxies:
        raise AnalyticsError("style.proxies must be a non-empty list")
    known_style_sources = set(benchmarks) | set(style_indices)
    seen_proxy_keys = set()
    for index, proxy in enumerate(proxies):
        proxy = _require_mapping(proxy, f"style.proxies[{index}]")
        for field in ("key", "label", "category", "long_key", "short_key",
                      "positive_label", "negative_label"):
            if not isinstance(proxy.get(field), str) or not proxy[field]:
                raise AnalyticsError(f"style.proxies[{index}].{field} must be a non-empty string")
        if proxy["key"] in seen_proxy_keys:
            raise AnalyticsError("style.proxies contains duplicate key {}".format(proxy["key"]))
        seen_proxy_keys.add(proxy["key"])
        for field in ("long_key", "short_key"):
            if proxy[field] not in known_style_sources:
                raise AnalyticsError(f"style.proxies[{index}].{field} references unknown source {proxy[field]}")

    strategies = _require_mapping(config.get("strategies"), "strategies")
    if not strategies:
        raise AnalyticsError("strategies must not be empty")
    for strategy_key, details in strategies.items():
        details = _require_mapping(details, f"strategies.{strategy_key}")
        if not isinstance(details.get("label"), str) or not details["label"]:
            raise AnalyticsError(f"strategies.{strategy_key}.label must be a string")
        benchmark_key = details.get("benchmark_key")
        if benchmark_key not in benchmarks:
            raise AnalyticsError(
                f"strategies.{strategy_key}.benchmark_key must reference benchmarks")

    anomalies = _require_mapping(config.get("anomalies"), "anomalies")
    for key in (
            "negative_weekly_percentile", "positive_weekly_percentile",
            "negative_rank_change_percentile_points", "consecutive_negative_weeks",
            "consecutive_positive_weeks", "weekly_excess_sigma",
            "min_history_weeks_for_drawdown", "drawdown_recovery_min"):
        anomalies[key] = _require_number(anomalies.get(key), f"anomalies.{key}", 0)
    if anomalies["negative_weekly_percentile"] > 1 or anomalies["positive_weekly_percentile"] > 1:
        raise AnalyticsError("weekly percentile thresholds must be <= 1")
    if anomalies["negative_weekly_percentile"] > anomalies["positive_weekly_percentile"]:
        raise AnalyticsError("negative weekly percentile must not exceed positive percentile")

    display = _require_mapping(config.get("display"), "display")
    display["percent_digits"] = int(_require_number(
        display.get("percent_digits"), "display.percent_digits", 0))
    display["max_focus_managers"] = int(_require_number(
        display.get("max_focus_managers"), "display.max_focus_managers", 1))
    display["max_alerts"] = int(_require_number(
        display.get("max_alerts"), "display.max_alerts", 1))
    return config


def load_focus_config(path: Path) -> dict[str, Any]:
    """Validate focus managers without requiring any particular manager to exist."""
    config = load_yaml(path)
    if config.get("version") != 1:
        raise AnalyticsError(f"{path}: version must be 1")
    managers = config.get("focus_managers")
    if not isinstance(managers, list):
        raise AnalyticsError("focus_managers must be a list")
    for index, manager in enumerate(managers):
        manager = _require_mapping(manager, f"focus_managers[{index}]")
        if not isinstance(manager.get("name"), str) or not manager["name"].strip():
            raise AnalyticsError(f"focus_managers[{index}].name must be a string")
        aliases = manager.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(item, str) for item in aliases):
            raise AnalyticsError(f"focus_managers[{index}].aliases must be a string list")
        strategies = manager.get("strategies", [])
        if not isinstance(strategies, list) or not all(isinstance(item, str) for item in strategies):
            raise AnalyticsError(f"focus_managers[{index}].strategies must be a string list")
        if manager.get("priority", "medium") not in ("high", "medium", "low"):
            raise AnalyticsError(f"focus_managers[{index}].priority is invalid")
        if not isinstance(manager.get("enabled", True), bool):
            raise AnalyticsError(f"focus_managers[{index}].enabled must be boolean")
        manager.setdefault("aliases", [])
        manager.setdefault("strategies", [])
        manager.setdefault("priority", "medium")
        manager.setdefault("enabled", True)
        manager.setdefault("note", "")
    return config
