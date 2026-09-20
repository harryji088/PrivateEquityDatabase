"""Read-only adapters for the production SQLite and benchmark JSON inputs."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from analytics.schemas import AnalyticsError, WeeklyObservation

REQUIRED_COLUMNS = {
    "fund_companies": {"id", "name"},
    "funds": {"id", "company_id", "strategy_type"},
    "weekly_performances": {
        "id", "fund_id", "record_date", "week_label", "weekly_return",
        "weekly_excess", "ytd_return", "ytd_excess", "ytd_excess_drawdown",
    },
}


def open_read_only_database(path: Path) -> sqlite3.Connection:
    """Open an existing SQLite database without allowing any write operation."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise AnalyticsError(f"SQLite database not found: {resolved}")
    try:
        connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection
    except sqlite3.Error as exc:
        raise AnalyticsError(f"Cannot open SQLite database {resolved}: {exc}") from exc


def load_observations(
        connection: sqlite3.Connection, strategies: dict[str, Any]) -> list[WeeklyObservation]:
    """Load reportable manager-strategy observations through one joined query."""
    try:
        actual = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        }
    except sqlite3.Error as exc:
        raise AnalyticsError(f"Cannot inspect SQLite schema: {exc}") from exc
    expected = set(REQUIRED_COLUMNS)
    missing = sorted(expected - actual)
    if missing:
        raise AnalyticsError("SQLite is missing required tables: {}".format(", ".join(missing)))

    for table, required_columns in REQUIRED_COLUMNS.items():
        try:
            actual_columns = {
                row[1] for row in connection.execute(f"PRAGMA table_info({table})")
            }
        except sqlite3.Error as exc:
            raise AnalyticsError(f"Cannot inspect SQLite table {table}: {exc}") from exc
        missing_columns = sorted(required_columns - actual_columns)
        if missing_columns:
            raise AnalyticsError(
                "SQLite table {} is missing required columns: {}".format(table, ", ".join(missing_columns)))

    placeholders = ", ".join("?" for _ in strategies)
    query = f"""
        SELECT wp.id AS source_row_id, wp.record_date, wp.week_label,
               fc.id AS manager_id, fc.name AS manager_name,
               f.strategy_type, wp.weekly_return, wp.weekly_excess,
               wp.ytd_return, wp.ytd_excess, wp.ytd_excess_drawdown
        FROM weekly_performances wp
        JOIN funds f ON f.id = wp.fund_id
        JOIN fund_companies fc ON fc.id = f.company_id
        WHERE f.strategy_type IN ({placeholders})
        ORDER BY wp.record_date, f.strategy_type, fc.name
    """
    try:
        rows = connection.execute(query, tuple(strategies)).fetchall()
    except sqlite3.Error as exc:
        raise AnalyticsError(f"Cannot load weekly observations: {exc}") from exc
    observations = []
    for row in rows:
        try:
            as_of_date = datetime.strptime(row["record_date"], "%Y-%m-%d").date()
        except (TypeError, ValueError) as exc:
            raise AnalyticsError("Invalid SQLite record_date: {!r}".format(row["record_date"])) from exc
        observations.append(WeeklyObservation(
            as_of_date=as_of_date,
            week_label=str(row["week_label"]),
            manager_id=int(row["manager_id"]),
            manager_name=str(row["manager_name"]),
            strategy_key=str(row["strategy_type"]),
            strategy_label=strategies[row["strategy_type"]]["label"],
            weekly_return=_as_float(row["weekly_return"], "weekly_return"),
            weekly_excess=_as_float(row["weekly_excess"], "weekly_excess"),
            ytd_return=_as_float(row["ytd_return"], "ytd_return"),
            ytd_excess=_as_float(row["ytd_excess"], "ytd_excess"),
            ytd_excess_drawdown=_as_float(
                row["ytd_excess_drawdown"], "ytd_excess_drawdown"),
            source_row_id=str(row["source_row_id"]),
        ))
    if not observations:
        raise AnalyticsError("No observations found for configured strategies")
    return observations


def available_dates(observations: Iterable[WeeklyObservation]) -> list[str]:
    return sorted({item.as_of_date.isoformat() for item in observations})


def load_benchmark_nav(path: Path, benchmarks: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map configured logical benchmark IDs to verified daily NAV observations."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        raise AnalyticsError(f"Cannot read benchmark JSON {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AnalyticsError(f"Invalid benchmark JSON {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise AnalyticsError("benchmark JSON top level must be an object")

    result = {}
    for logical_key, details in benchmarks.items():
        source_key = details["source_key"]
        item = raw.get(source_key)
        if not isinstance(item, dict):
            raise AnalyticsError(f"Benchmark source {source_key} is missing")
        dates = item.get("dates")
        navs = item.get("navs")
        if not isinstance(dates, list) or not isinstance(navs, list) or len(dates) != len(navs):
            raise AnalyticsError(f"Benchmark source {source_key} has mismatched dates/navs")
        nav_by_date = {}
        for item_date, nav in zip(dates, navs):
            if not isinstance(item_date, str):
                raise AnalyticsError(f"Benchmark source {source_key} has non-string date")
            try:
                datetime.strptime(item_date, "%Y%m%d")
                numeric_nav = float(nav)
            except (TypeError, ValueError) as exc:
                raise AnalyticsError(f"Benchmark source {source_key} has invalid observation") from exc
            if not math.isfinite(numeric_nav) or numeric_nav <= 0:
                raise AnalyticsError(f"Benchmark source {source_key} has non-positive NAV")
            nav_by_date[item_date] = numeric_nav
        if not nav_by_date:
            raise AnalyticsError(f"Benchmark source {source_key} is empty")
        result[logical_key] = {
            "benchmark_key": logical_key,
            "label": details["label"],
            "source_key": source_key,
            "nav_by_date": nav_by_date,
        }
    return result


def load_style_nav(path: Path, style_indices: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Load locally cached V2A style-index NAVs keyed by configured logical ID."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        raise AnalyticsError(f"Cannot read style index JSON {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AnalyticsError(f"Invalid style index JSON {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise AnalyticsError("style index JSON top level must be an object")

    result = {}
    for logical_key, details in style_indices.items():
        source_key = details["source_key"]
        item = raw.get(source_key)
        if not isinstance(item, dict):
            raise AnalyticsError(f"Style index source {source_key} is missing")
        for field in ("label", "wind_code", "csindex_code"):
            expected = details[field]
            actual = item.get(field)
            if actual != expected:
                raise AnalyticsError(
                    f"Style index source {source_key} has mismatched {field}: "
                    f"expected {expected!r}, got {actual!r}")
        dates = item.get("dates")
        navs = item.get("navs")
        if not isinstance(dates, list) or not isinstance(navs, list) or len(dates) != len(navs):
            raise AnalyticsError(f"Style index source {source_key} has mismatched dates/navs")
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise AnalyticsError(
                f"Style index source {source_key} dates must be sorted and unique")
        nav_by_date = {}
        for item_date, nav in zip(dates, navs):
            if not isinstance(item_date, str):
                raise AnalyticsError(f"Style index source {source_key} has non-string date")
            try:
                datetime.strptime(item_date, "%Y%m%d")
                numeric_nav = float(nav)
            except (TypeError, ValueError) as exc:
                raise AnalyticsError(f"Style index source {source_key} has invalid observation") from exc
            if not math.isfinite(numeric_nav) or numeric_nav <= 0:
                raise AnalyticsError(f"Style index source {source_key} has non-positive NAV")
            nav_by_date[item_date] = numeric_nav
        if not nav_by_date:
            raise AnalyticsError(f"Style index source {source_key} is empty")
        result[logical_key] = {
            "style_key": logical_key,
            "label": details["label"],
            "source_key": source_key,
            "wind_code": details["wind_code"],
            "nav_by_date": nav_by_date,
        }
    return result


def _as_float(value: Any, label: str):
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AnalyticsError(f"SQLite {label} must be numeric") from exc
    if not math.isfinite(result):
        raise AnalyticsError(f"SQLite {label} must be finite")
    return result
