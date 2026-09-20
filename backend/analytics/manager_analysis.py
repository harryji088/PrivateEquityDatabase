"""Watchlist cards derived from already-ranked manager-strategy facts."""

from __future__ import annotations

from typing import Any

from analytics.metrics import trailing_complete_values
from analytics.schemas import WeeklyObservation


def build_focus_manager_cards(
        focus_config: dict[str, Any], universe: dict[str, Any],
        observations: list[WeeklyObservation], report_dates: list[str], as_of_date: str,
        strategies: dict[str, Any], benchmark_returns: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve configured names and turn current ranked records into Watchlist cards."""
    rank_lookup = {}
    for summary in universe["strategy_summary"]:
        for record in summary["ranked_managers"]:
            rank_lookup[(record["manager_name"], record["strategy_key"])] = record
    historical_observations = [
        item for item in observations if item.as_of_date.isoformat() <= as_of_date
    ]
    available_names = {item.manager_name for item in historical_observations}
    histories = universe["histories"]
    cards = []
    warnings = []

    for order, configured in enumerate(focus_config["focus_managers"]):
        if not configured["enabled"]:
            continue
        configured_names = [configured["name"]] + configured["aliases"]
        exact_primary = configured["name"] if configured["name"] in available_names else None
        alias_matches = sorted(available_names.intersection(configured_names))
        if exact_primary:
            manager_name = exact_primary
        elif len(alias_matches) == 1:
            manager_name = alias_matches[0]
        elif len(alias_matches) > 1:
            warnings.append("重点管理人 {} 匹配多个数据库名称：{}".format(
                configured["name"], ", ".join(alias_matches)))
            continue
        else:
            warnings.append("未在数据库中找到重点管理人：{}".format(configured["name"]))
            cards.append({
                "manager_name": configured["name"],
                "priority": configured["priority"],
                "status": "missing_manager",
                "data_quality": {"status": "warning", "warnings": [warnings[-1]]},
                "_config_order": order,
            })
            continue

        if configured["strategies"]:
            allowed_strategies = configured["strategies"]
        else:
            # An empty list means every *available* V1 strategy for this manager,
            # not every strategy in the global configuration.
            allowed_strategies = [
                strategy_key for strategy_key in strategies
                if any(item.manager_name == manager_name and item.strategy_key == strategy_key
                       for item in historical_observations)
            ]
        cards_for_manager = 0
        for strategy_key in allowed_strategies:
            if strategy_key not in strategies:
                warnings.append("重点管理人 {} 配置了未支持策略 {}".format(
                    configured["name"], strategy_key))
                continue
            current = rank_lookup.get((manager_name, strategy_key))
            if not current:
                warning = "重点管理人 {} 在 {} 没有 {} 有效观测".format(
                    manager_name, as_of_date, strategies[strategy_key]["label"])
                warnings.append(warning)
                cards.append({
                    "manager_name": manager_name,
                    "strategy_key": strategy_key,
                    "strategy_label": strategies[strategy_key]["label"],
                    "priority": configured["priority"],
                    "note": configured["note"],
                    "status": "missing_current_observation",
                    "alerts": [],
                    "data_quality": {"status": "warning", "warnings": [warning]},
                    "_config_order": order,
                })
                cards_for_manager += 1
                continue
            history = histories[(current["manager_id"], strategy_key)]
            four_values = trailing_complete_values(
                {item_date: item.weekly_excess for item_date, item in history.items()},
                report_dates, as_of_date, 4)
            cards.append({
                "manager_name": manager_name,
                "strategy_key": strategy_key,
                "strategy_label": strategies[strategy_key]["label"],
                "priority": configured["priority"],
                "note": configured["note"],
                "current": {
                    "manager_strategy_return": current["weekly_return"],
                    "benchmark_return": benchmark_returns.get(strategy_key),
                    "excess_return": current["weekly_excess"],
                    "rank": current["rank"],
                    "rank_total": current["rank_total"],
                    "peer_percentile": current["peer_percentile"],
                },
                "recent": {
                    "weeks_4_cumulative_excess": current["rolling"].get(
                        "weeks_4", {}).get("cumulative_excess"),
                    "weeks_4_positive_count": sum(value > 0 for value in four_values) if four_values else None,
                    "weeks_4_observation_count": len(four_values) if four_values else 0,
                    "ytd_excess": current["ytd_excess"],
                    "current_excess_drawdown": current["ytd_excess_drawdown"],
                },
                "comparison": {
                    "previous_rank": current["previous_rank"],
                    "rank_change": current["rank_change"],
                    "previous_excess": current["previous_excess"],
                    "peer_percentile_change": current["peer_percentile_change"],
                },
                "alerts": [],
                "data_quality": {"status": "ok", "warnings": []},
                "_config_order": order,
            })
            cards_for_manager += 1
        if cards_for_manager == 0:
            warnings.append(f"重点管理人 {manager_name} 没有可用的当前策略")

    priority_order = {"high": 0, "medium": 1, "low": 2}
    cards.sort(key=lambda item: (priority_order.get(item.get("priority"), 3), item.get("_config_order", 0),
                                 item.get("strategy_key", "")))
    for card in cards:
        card.pop("_config_order", None)
    return cards, warnings
