"""Structured, deterministic anomaly rules for manager-strategy observations."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from analytics.metrics import quantile
from analytics.schemas import WeeklyObservation


def detect_anomalies(
        universe: dict[str, Any], observations: list[WeeklyObservation], as_of_date: str,
        config: dict[str, Any], focus_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate V1 rules and merge all hits for each manager-strategy pair."""
    thresholds = config["anomalies"]
    min_sample = config["report"]["min_sample_size"]
    grouped = defaultdict(list)
    histories = universe["histories"]
    priority_lookup = _focus_priorities(focus_config)
    strategy_labels = {
        item["strategy_key"]: item["strategy_label"]
        for item in universe["strategy_summary"]
    }

    for summary in universe["strategy_summary"]:
        if summary["sample_size"] < min_sample:
            continue
        stats = summary["excess_return"]
        weekly_values = [item["weekly_excess"] for item in summary["ranked_managers"]]
        negative_cutoff = quantile(weekly_values, thresholds["negative_weekly_percentile"])
        positive_cutoff = quantile(weekly_values, thresholds["positive_weekly_percentile"])
        for record in summary["ranked_managers"]:
            key = (record["manager_name"], record["strategy_key"])
            excess = record["weekly_excess"]
            if excess <= negative_cutoff:
                _add(grouped, key, "negative", "WEEKLY_EXCESS_BOTTOM_DECILE", {
                    "weekly_excess": excess, "peer_cutoff": negative_cutoff,
                    "peer_percentile": record["peer_percentile"],
                }, "本周超额位于同类后{}%".format(int(thresholds["negative_weekly_percentile"] * 100)))
            if stats["std"] and excess <= stats["mean"] - thresholds["weekly_excess_sigma"] * stats["std"]:
                _add(grouped, key, "negative", "WEEKLY_EXCESS_2SIGMA_NEGATIVE", {
                    "weekly_excess": excess, "peer_mean": stats["mean"], "peer_std": stats["std"],
                }, "本周超额低于同类均值两个标准差")
            if excess >= positive_cutoff:
                _add(grouped, key, "positive", "WEEKLY_EXCESS_TOP_DECILE", {
                    "weekly_excess": excess, "peer_cutoff": positive_cutoff,
                    "peer_percentile": record["peer_percentile"],
                }, "本周超额位于同类前%s%%" % (100 - int(thresholds["positive_weekly_percentile"] * 100)))
            if record["consecutive_negative_weeks"] >= thresholds["consecutive_negative_weeks"]:
                _add(grouped, key, "negative", "CONSECUTIVE_NEGATIVE_EXCESS", {
                    "consecutive_negative_weeks": record["consecutive_negative_weeks"],
                }, "连续负超额")
            if record["consecutive_positive_weeks"] >= thresholds["consecutive_positive_weeks"]:
                _add(grouped, key, "positive", "CONSECUTIVE_POSITIVE_EXCESS", {
                    "consecutive_positive_weeks": record["consecutive_positive_weeks"],
                }, "连续正超额")

            change = record["peer_percentile_change"]
            point_threshold = thresholds["negative_rank_change_percentile_points"] / 100.0
            if change is not None and change <= -point_threshold:
                _add(grouped, key, "negative", "PEER_PERCENTILE_DECLINE", {
                    "peer_percentile_change": change, "threshold": -point_threshold,
                    "rank_change": record["rank_change"],
                }, "同类百分位显著下降")
            if change is not None and change >= point_threshold:
                _add(grouped, key, "positive", "PEER_PERCENTILE_IMPROVEMENT", {
                    "peer_percentile_change": change, "threshold": point_threshold,
                    "rank_change": record["rank_change"],
                }, "同类百分位显著提升")

            _detect_rolling(
                grouped, key, record, summary, "weeks_4", "4周", min_sample)
            _detect_drawdown(grouped, key, record, histories, thresholds, as_of_date)

    alerts = []
    for (manager_name, strategy_key, severity), hits in grouped.items():
        alerts.append({
            "severity": severity,
            "codes": [item["code"] for item in hits],
            "manager_name": manager_name,
            "strategy_key": strategy_key,
            "strategy_label": strategy_labels[strategy_key],
            "as_of_date": as_of_date,
            "evidence": {item["code"]: item["evidence"] for item in hits},
            "message_templates": [item["message"] for item in hits],
            "focus_priority": priority_lookup.get(manager_name, "low"),
        })
    priority_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda item: (
        0 if item["severity"] == "negative" else 1,
        -len(item["codes"]), priority_order.get(item["focus_priority"], 3),
        item["manager_name"], item["strategy_key"],
    ))
    return alerts


def _detect_rolling(grouped, key, record, summary, window_key, label, min_sample):
    rolling = summary["rolling"].get(window_key, {})
    value = record["rolling"].get(window_key, {}).get("cumulative_excess")
    if value is None or rolling.get("sample_size", 0) < min_sample:
        return
    if value <= rolling["p10"]:
        _add(grouped, key, "negative", f"{window_key.upper()}_EXCESS_BOTTOM_DECILE", {
            "cumulative_excess": value, "peer_p10": rolling["p10"], "window": label,
        }, f"近{label}累计超额位于同类后10%")
    if value >= rolling["p90"]:
        _add(grouped, key, "positive", f"{window_key.upper()}_EXCESS_TOP_DECILE", {
            "cumulative_excess": value, "peer_p90": rolling["p90"], "window": label,
        }, f"近{label}累计超额位于同类前10%")


def _detect_drawdown(grouped, key, record, histories, thresholds, as_of_date):
    history = histories[(record["manager_id"], record["strategy_key"])]
    ordered = [history[item_date] for item_date in sorted(history) if item_date <= as_of_date]
    drawdowns = [item.ytd_excess_drawdown for item in ordered if item.ytd_excess_drawdown is not None]
    current = record["ytd_excess_drawdown"]
    if current is None:
        return
    if len(drawdowns) >= int(thresholds["min_history_weeks_for_drawdown"]):
        p10 = quantile(drawdowns, 0.10)
        if current <= p10:
            _add(grouped, key, "negative", "EXCESS_DRAWDOWN_BOTTOM_DECILE", {
                "current_excess_drawdown": current, "historical_p10": p10,
                "history_weeks": len(drawdowns),
            }, "当前超额回撤处于自身历史最差10%")
    if len(drawdowns) >= 2:
        previous = drawdowns[-2]
        prior_cycle = drawdowns[:-1]
        last_high_index = max(
            (index for index, value in enumerate(prior_cycle) if value >= 0),
            default=-1,
        )
        cycle_drawdowns = prior_cycle[last_high_index + 1:]
        prior_low = min(cycle_drawdowns) if cycle_drawdowns else None
        recovery = current - prior_low if prior_low is not None else None
        previous_recovery = previous - prior_low if prior_low is not None else None
        recovery_threshold = thresholds["drawdown_recovery_min"]
        if (
                prior_low is not None and prior_low < 0 and current < 0
                and current > previous
                and previous_recovery < recovery_threshold <= recovery):
            _add(grouped, key, "positive", "EXCESS_DRAWDOWN_RECOVERY", {
                "current_excess_drawdown": current, "prior_drawdown_low": prior_low,
                "previous_excess_drawdown": previous, "recovery": recovery,
            }, "超额回撤明显修复")


def _add(grouped, key, severity, code, evidence, message):
    grouped[(key[0], key[1], severity)].append({
        "severity": severity, "code": code, "evidence": evidence, "message": message,
    })


def _focus_priorities(config: dict[str, Any]) -> dict[str, str]:
    result = {}
    for manager in config["focus_managers"]:
        if manager["enabled"]:
            for name in [manager["name"]] + manager["aliases"]:
                result[name] = manager["priority"]
    return result
