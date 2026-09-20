"""Deterministic V2A style-proxy analysis on the report's weekly calendar."""

from __future__ import annotations

from datetime import datetime
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


def _leg_return(
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


def _spread_result(
        long_leg: dict[str, Any], short_leg: dict[str, Any], status: str,
        reason: str | None, spread: float | None = None) -> dict[str, Any]:
    return {
        "spread": spread,
        "long_return": long_leg["return"],
        "short_return": short_leg["return"],
        "long_start_nav_date": long_leg["start_nav_date"],
        "long_end_nav_date": long_leg["end_nav_date"],
        "short_start_nav_date": short_leg["start_nav_date"],
        "short_end_nav_date": short_leg["end_nav_date"],
        "status": status,
        "reason": reason,
    }


def _lag_days(actual_date: str, target_date: str) -> int:
    actual = datetime.strptime(actual_date, "%Y%m%d").date()
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    return (target - actual).days


def _aligned_spread(
        long_series: dict[str, Any], short_series: dict[str, Any],
        start_date: str, end_date: str, max_staleness_days: int) -> dict[str, Any]:
    long_leg = _leg_return(long_series["nav_by_date"], start_date, end_date)
    short_leg = _leg_return(short_series["nav_by_date"], start_date, end_date)
    if long_leg["return"] is None or short_leg["return"] is None:
        return _spread_result(long_leg, short_leg, "incomplete", "缺少指数日线")
    if (long_leg["start_nav_date"] != short_leg["start_nav_date"] or
            long_leg["end_nav_date"] != short_leg["end_nav_date"]):
        return _spread_result(
            long_leg, short_leg, "incomplete", "两条指数实际取值日期不一致")

    start_actual = long_leg["start_nav_date"]
    end_actual = long_leg["end_nav_date"]
    start_lag = _lag_days(start_actual, start_date)
    end_lag = _lag_days(end_actual, end_date)
    if start_lag > max_staleness_days or end_lag > max_staleness_days:
        return _spread_result(
            long_leg, short_leg, "incomplete",
            f"指数数据滞后（起点 {start_lag} 天，终点 {end_lag} 天）")
    if end_actual <= start_actual:
        return _spread_result(
            long_leg, short_leg, "incomplete", "窗口内没有新增指数观测")

    result = _spread_result(
        long_leg, short_leg, "ok", None,
        long_leg["return"] - short_leg["return"])
    result["start_lag_days"] = start_lag
    result["end_lag_days"] = end_lag
    if start_lag or end_lag:
        result["freshness_warning"] = (
            f"使用最近可用交易日（起点滞后 {start_lag} 天，终点滞后 {end_lag} 天）")
    else:
        result["freshness_warning"] = None
    return result


def _spread_sign(spread: float | None, neutral_threshold: float) -> int | None:
    if spread is None:
        return None
    if spread > neutral_threshold:
        return 1
    if spread < -neutral_threshold:
        return -1
    return 0


def _direction(
        spread: float | None, proxy: dict[str, Any], neutral_threshold: float) -> str | None:
    sign = _spread_sign(spread, neutral_threshold)
    if sign is None:
        return None
    if sign > 0:
        return proxy["positive_label"]
    if sign < 0:
        return proxy["negative_label"]
    return "相对持平"


def _weekly_history(
        long_series: dict[str, Any], short_series: dict[str, Any], report_dates: list[str],
        as_of_date: str, max_weeks: int, max_staleness_days: int) -> list[dict[str, Any]]:
    end = report_dates.index(as_of_date)
    start = max(0, end - max_weeks + 1)
    result = []
    for index in range(start, end + 1):
        end_date = report_dates[index]
        start_date = report_dates[index - 1] if index else _year_start_anchor(end_date)
        point = _aligned_spread(
            long_series, short_series, start_date, end_date, max_staleness_days)
        point["as_of_date"] = end_date
        result.append(point)
    return result


def _stability(history: list[dict[str, Any]], neutral_threshold: float) -> dict[str, Any]:
    usable = [item["spread"] for item in history if item["spread"] is not None]
    switches = 0
    prior_sign = None
    for value in usable:
        sign = _spread_sign(value, neutral_threshold)
        if prior_sign is not None and sign and prior_sign and sign != prior_sign:
            switches += 1
        if sign:
            prior_sign = sign

    streak = 0
    final_sign = None
    for item in reversed(history):
        value = item["spread"]
        if value is None:
            break
        sign = _spread_sign(value, neutral_threshold)
        if not sign:
            break
        if final_sign is None:
            final_sign = sign
        if sign != final_sign:
            break
        streak += 1
    return {
        "available_week_count": len(usable),
        "switch_count": switches,
        "current_streak_weeks": streak,
    }


def _window_conclusion(
        items: list[dict[str, Any]], window_key: str) -> dict[str, Any]:
    """Summarize one category only when all usable proxies point the same way."""
    observations = []
    for item in items:
        point = item["weekly"] if window_key == "weekly" else item["rolling"].get(window_key, {})
        spread = point.get("spread")
        if point.get("status") != "ok" or spread is None:
            continue
        sign = point.get("sign")
        observations.append({
            "sign": sign,
            "direction": point.get("direction") or "相对持平",
        })

    available_count = len(observations)
    if available_count != len(items):
        return {
            "state": "incomplete", "sign": None,
            "label": f"数据不完整（{available_count}/{len(items)} 可用）",
            "available_proxy_count": available_count,
            "configured_proxy_count": len(items),
        }

    positive = [item for item in observations if item["sign"] > 0]
    negative = [item for item in observations if item["sign"] < 0]
    neutral = [item for item in observations if item["sign"] == 0]
    if len(positive) == available_count:
        labels = list(dict.fromkeys(item["direction"] for item in positive))
        state, sign, label = "unanimous", 1, "；".join(labels)
    elif len(negative) == available_count:
        labels = list(dict.fromkeys(item["direction"] for item in negative))
        state, sign, label = "unanimous", -1, "；".join(labels)
    elif len(neutral) == available_count:
        state, sign, label = "flat", 0, "相对持平"
    else:
        state, sign = "mixed", None
        label = (
            f"信号分化（多头腿占优 {len(positive)}/{available_count}，"
            f"对照腿占优 {len(negative)}/{available_count}）"
        )
    return {
        "state": state,
        "sign": sign,
        "label": label,
        "available_proxy_count": available_count,
        "configured_proxy_count": len(items),
    }


def _trend_comment(
        weekly: dict[str, Any], weeks_4: dict[str, Any],
        weeks_12: dict[str, Any]) -> str:
    """Describe agreement across windows, without inferring a causal regime change."""
    if weekly["state"] in ("unavailable", "incomplete"):
        return "本周数据不足，未判断趋势"
    if weekly["state"] in ("mixed", "flat"):
        return "本周未形成一致方向"
    if weeks_4["state"] in ("unavailable", "incomplete"):
        return "近4周历史不足，未判断持续性"
    if weeks_4["state"] in ("mixed", "flat"):
        return "近4周信号分化，本周方向尚待确认"
    if weekly["sign"] == weeks_4["sign"]:
        if weeks_12["state"] == "unanimous" and weeks_12["sign"] == weekly["sign"]:
            return "本周、近4周与近12周方向一致"
        if weeks_12["state"] == "unanimous":
            return "本周与近4周延续，但与近12周方向相反"
        return "本周与近4周方向一致"
    if weeks_12["state"] == "unanimous" and weeks_12["sign"] == weeks_4["sign"]:
        return "短线反转；近4周与近12周主导方向未变"
    if weeks_12["state"] == "unanimous" and weeks_12["sign"] == weekly["sign"]:
        return "本周与近12周同向，近4周出现反向波动"
    return "本周与近4周方向相反，尚待确认"


def _category_conclusions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return fixed, renderer-ready conclusions grouped by configured proxy category."""
    by_category = {}
    for item in items:
        by_category.setdefault(item["category"], []).append(item)
    conclusions = []
    for category, category_items in by_category.items():
        weekly = _window_conclusion(category_items, "weekly")
        weeks_4 = _window_conclusion(category_items, "weeks_4")
        weeks_12 = _window_conclusion(category_items, "weeks_12")
        conclusions.append({
            "category": category,
            "weekly": weekly,
            "weeks_4": weeks_4,
            "weeks_12": weeks_12,
            "trend_comment": _trend_comment(weekly, weeks_4, weeks_12),
        })
    return conclusions


def _style_headline(conclusions: list[dict[str, Any]]) -> str:
    """Create a compact, facts-only headline for the report's first section."""
    if not conclusions:
        return "风格代理数据不足"
    weekly_signals = []
    reversals = []
    for item in conclusions:
        weekly = item["weekly"]
        if weekly["state"] == "unanimous":
            weekly_signals.append("{}：{}".format(item["category"], weekly["label"]))
        elif weekly["state"] == "mixed":
            weekly_signals.append("{}：信号分化".format(item["category"]))
        else:
            weekly_signals.append("{}：{}".format(item["category"], weekly["label"]))
        if item["trend_comment"].startswith("短线反转"):
            reversals.append(item["category"])
    headline = "本周：{}。".format("；".join(weekly_signals))
    if reversals:
        headline += "{}出现短线反转，尚待确认。".format("、".join(reversals))
    return headline


def analyze_style_proxies(
        sources: dict[str, dict[str, Any]], proxies: list[dict[str, Any]],
        report_dates: list[str], as_of_date: str, previous_as_of_date: str | None,
        recent_windows: list[int], heatmap_weeks: int, max_staleness_days: int = 4,
        neutral_spread_threshold: float = 0.0005) -> dict[str, Any]:
    """Build V2A style facts without looking after the report date."""
    warnings = []
    analyzed = []
    weekly_start = previous_as_of_date or _year_start_anchor(as_of_date)
    current_index = report_dates.index(as_of_date)

    for proxy in proxies:
        long_series = sources.get(proxy["long_key"])
        short_series = sources.get(proxy["short_key"])
        if long_series is None or short_series is None:
            missing = [key for key in (proxy["long_key"], proxy["short_key"])
                       if key not in sources]
            item = {
                "style_key": proxy["key"], "label": proxy["label"],
                "category": proxy["category"], "long_key": proxy["long_key"],
                "short_key": proxy["short_key"], "weekly": {
                    "spread": None, "status": "incomplete",
                    "reason": "未配置指数：{}".format(", ".join(missing)),
                }, "rolling": {}, "history": [],
                "stability": {"available_week_count": 0, "switch_count": 0,
                              "current_streak_weeks": 0},
            }
            warnings.append("{}：{}".format(proxy["label"], item["weekly"]["reason"]))
            analyzed.append(item)
            continue

        weekly = _aligned_spread(
            long_series, short_series, weekly_start, as_of_date, max_staleness_days)
        weekly["sign"] = _spread_sign(weekly["spread"], neutral_spread_threshold)
        weekly["direction"] = _direction(
            weekly["spread"], proxy, neutral_spread_threshold)
        if weekly["status"] != "ok":
            warnings.append("{}：{}".format(proxy["label"], weekly["reason"]))
        elif weekly.get("freshness_warning"):
            warnings.append("{}：{}".format(proxy["label"], weekly["freshness_warning"]))

        rolling = {}
        for window in recent_windows:
            start_index = current_index - window
            if start_index == -1:
                start_date = _year_start_anchor(as_of_date)
            elif start_index < -1:
                rolling[f"weeks_{window}"] = {
                    "spread": None, "status": "insufficient_history", "reason": "周度历史不足",
                }
                continue
            else:
                start_date = report_dates[start_index]
            value = _aligned_spread(
                long_series, short_series, start_date, as_of_date, max_staleness_days)
            value["sign"] = _spread_sign(value["spread"], neutral_spread_threshold)
            value["direction"] = _direction(
                value["spread"], proxy, neutral_spread_threshold)
            rolling[f"weeks_{window}"] = value

        history = _weekly_history(
            long_series, short_series, report_dates, as_of_date, heatmap_weeks,
            max_staleness_days)
        for point in history:
            point["sign"] = _spread_sign(point["spread"], neutral_spread_threshold)
            point["direction"] = _direction(
                point["spread"], proxy, neutral_spread_threshold)
        analyzed.append({
            "style_key": proxy["key"], "label": proxy["label"], "category": proxy["category"],
            "long_key": proxy["long_key"], "short_key": proxy["short_key"],
            "weekly": weekly, "rolling": rolling, "history": history,
            "stability": _stability(history, neutral_spread_threshold),
        })

    ready = [item for item in analyzed if item["weekly"]["status"] == "ok"]
    category_conclusions = _category_conclusions(analyzed)
    return {
        "proxies": analyzed,
        "summary": {
            "configured_proxy_count": len(analyzed),
            "available_proxy_count": len(ready),
            "heatmap_weeks": heatmap_weeks,
            "category_conclusions": category_conclusions,
            "headline": _style_headline(category_conclusions),
            "max_staleness_days": max_staleness_days,
            "neutral_spread_threshold": neutral_spread_threshold,
        },
        "warnings": warnings,
    }
