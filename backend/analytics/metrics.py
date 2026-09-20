"""Small deterministic statistical primitives used by the report."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any


def valid_values(values: Iterable[float | None]) -> list[float]:
    """Return finite numeric values, without treating missing values as zero."""
    result = []
    for value in values:
        if value is not None and math.isfinite(float(value)):
            result.append(float(value))
    return result


def quantile(values: Iterable[float | None], percentile: float) -> float | None:
    """Linear quantile: position = percentile * (n - 1)."""
    if percentile < 0 or percentile > 1:
        raise ValueError("percentile must be between 0 and 1")
    sorted_values = sorted(valid_values(values))
    if not sorted_values:
        return None
    position = percentile * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def safe_mean(values: Iterable[float | None]) -> float | None:
    cleaned = valid_values(values)
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def safe_std(values: Iterable[float | None]) -> float | None:
    """Population standard deviation; a single valid observation has zero spread."""
    cleaned = valid_values(values)
    if not cleaned:
        return None
    mean = sum(cleaned) / len(cleaned)
    return math.sqrt(sum((value - mean) ** 2 for value in cleaned) / len(cleaned))


def descriptive_stats(values: Iterable[float | None]) -> dict[str, float | None]:
    cleaned = valid_values(values)
    if not cleaned:
        return {
            "mean": None, "p25": None, "median": None, "p75": None,
            "min": None, "max": None, "std": None,
        }
    p25 = quantile(cleaned, 0.25)
    p75 = quantile(cleaned, 0.75)
    return {
        "mean": safe_mean(cleaned),
        "p25": p25,
        "median": quantile(cleaned, 0.50),
        "p75": p75,
        "min": min(cleaned),
        "max": max(cleaned),
        "std": safe_std(cleaned),
    }


def positive_ratio(values: Iterable[float | None]) -> float | None:
    cleaned = valid_values(values)
    if not cleaned:
        return None
    return sum(value > 0 for value in cleaned) / len(cleaned)


def percentile_from_rank(rank: int, total: int) -> float | None:
    if total <= 1:
        return None
    return (total - rank) / (total - 1)


def rank_desc(records: Iterable[dict[str, Any]], value_key: str, name_key: str) -> list[dict[str, Any]]:
    """Rank finite values descending, resolving ties by name ascending."""
    eligible = [record for record in records if record.get(value_key) is not None]
    eligible.sort(key=lambda item: (-float(item[value_key]), str(item[name_key])))
    total = len(eligible)
    ranked = []
    for index, record in enumerate(eligible, start=1):
        item = dict(record)
        item["rank"] = index
        item["rank_total"] = total
        item["peer_percentile"] = percentile_from_rank(index, total)
        ranked.append(item)
    return ranked


def trailing_complete_values(
        values_by_date: dict[str, float | None], dates: list[str], as_of_date: str,
        window: int) -> list[float] | None:
    """Get an exact, gap-free trailing window ending at ``as_of_date``."""
    if as_of_date not in dates:
        return None
    end = dates.index(as_of_date) + 1
    start = end - window
    if start < 0:
        return None
    window_dates = dates[start:end]
    values = [values_by_date.get(item) for item in window_dates]
    if any(value is None for value in values):
        return None
    return [float(value) for value in values if value is not None]


def consecutive_sign_count(values: Iterable[float | None], positive: bool) -> int:
    """Count consecutive strict positive or negative observations from the end."""
    count = 0
    for value in reversed(list(values)):
        if value is None:
            break
        if (positive and value > 0) or (not positive and value < 0):
            count += 1
        else:
            break
    return count


def drawdown_from_series(values: Iterable[float | None]) -> list[float | None]:
    """Relative drawdown for a NAV-like series; missing observations stay missing."""
    peak = None
    result = []
    for value in values:
        if value is None:
            result.append(None)
            continue
        numeric = float(value)
        if peak is None or numeric > peak:
            peak = numeric
        result.append((numeric - peak) / peak if peak else None)
    return result
