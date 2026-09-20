"""Analysis of daily benchmark NAV data on the report's weekly calendar."""

from __future__ import annotations

from typing import Any


def _year_start_anchor(report_date: str) -> str:
    return "%s-12-31" % (int(report_date[:4]) - 1)


def _nearest_nav_on_or_before(
        nav_by_date: dict[str, float], target_date: str) -> tuple[str | None, float | None]:
    target = target_date.replace("-", "")
    candidates = [item for item in nav_by_date if item <= target]
    if not candidates:
        return None, None
    actual_date = max(candidates)
    return actual_date, nav_by_date[actual_date]


def _period_return(
        nav_by_date: dict[str, float], start_date: str, end_date: str) -> dict[str, Any]:
    start_actual, start_nav = _nearest_nav_on_or_before(nav_by_date, start_date)
    end_actual, end_nav = _nearest_nav_on_or_before(nav_by_date, end_date)
    if start_nav is None or end_nav is None:
        return {
            "return": None,
            "start_nav_date": start_actual,
            "end_nav_date": end_actual,
        }
    return {
        "return": end_nav / start_nav - 1.0,
        "start_nav_date": start_actual,
        "end_nav_date": end_actual,
    }


def analyze_benchmarks(
        benchmarks: dict[str, dict[str, Any]], report_dates: list[str], as_of_date: str,
        previous_as_of_date: str | None, recent_windows: list[int]) -> dict[str, Any]:
    """Align daily NAVs to report dates without ever looking beyond a report date."""
    market = []
    warnings = []
    for benchmark_key, benchmark in sorted(benchmarks.items()):
        nav_by_date = benchmark["nav_by_date"]
        weekly_start = previous_as_of_date or _year_start_anchor(as_of_date)
        weekly = _period_return(nav_by_date, weekly_start, as_of_date)
        if not previous_as_of_date and weekly["start_nav_date"] != weekly_start.replace("-", ""):
            warnings.append(
                f"{benchmark_key} is missing year-start anchor {weekly_start}")

        rolling = {}
        current_index = report_dates.index(as_of_date)
        for window in recent_windows:
            key = f"weeks_{window}"
            start_index = current_index - window
            if start_index == -1:
                start_report_date = _year_start_anchor(as_of_date)
            elif start_index < -1:
                rolling[key] = {
                    "return": None, "start_report_date": None,
                    "start_nav_date": None, "end_nav_date": None,
                }
                continue
            else:
                start_report_date = report_dates[start_index]
            result = _period_return(nav_by_date, start_report_date, as_of_date)
            result["start_report_date"] = start_report_date
            rolling[key] = result

        actual_as_of, _ = _nearest_nav_on_or_before(nav_by_date, as_of_date)
        if actual_as_of != as_of_date.replace("-", ""):
            warnings.append(
                "{} uses benchmark NAV date {} for report date {}".format(benchmark_key, actual_as_of or "missing", as_of_date))
        market.append({
            "benchmark_key": benchmark_key,
            "benchmark_label": benchmark["label"],
            "source_key": benchmark["source_key"],
            "as_of_date": as_of_date,
            "as_of_nav_date": actual_as_of,
            "weekly_return": weekly["return"],
            "previous_nav_date": weekly["start_nav_date"],
            "rolling": rolling,
        })

    by_key = {item["benchmark_key"]: item for item in market}
    style_proxies = []
    for large_key, small_key, label in (
            ("CSI300", "CSI1000", "沪深300 - 中证1000"),
            ("CSI500", "CSI2000", "中证500 - 中证2000")):
        large = by_key.get(large_key, {}).get("weekly_return")
        small = by_key.get(small_key, {}).get("weekly_return")
        if large is None or small is None:
            style_proxies.append({"label": label, "weekly_difference": None, "status": "风格信号不完整"})
        else:
            difference = large - small
            style_proxies.append({
                "label": label,
                "weekly_difference": difference,
                "status": "大盘相对占优" if difference > 0 else "小盘相对占优",
            })

    usable = [item for item in style_proxies if item["weekly_difference"] is not None]
    if not usable:
        environment = "无法判断"
    elif all(item["weekly_difference"] > 0 for item in usable):
        environment = "大盘相对占优"
    elif all(item["weekly_difference"] < 0 for item in usable):
        environment = "小盘相对占优"
    else:
        environment = "风格信号不完整"
    return {
        "benchmarks": market,
        "style_proxies": style_proxies,
        "environment_label": environment,
        "warnings": warnings,
    }
