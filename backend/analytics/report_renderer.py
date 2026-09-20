"""Deterministic Markdown rendering from precomputed report facts only."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# The report is read left-to-right in the same order every week.  Keep this
# presentation decision in the template rather than relying on YAML/dict order.
STRATEGY_TEMPLATE_ORDER = (
    "index_300", "index_a500", "index_500", "index_1000", "index_2000",
)
BENCHMARK_TEMPLATE_ORDER = (
    "CSI300", "A500", "CSI500", "CSI1000", "CSI2000",
)


def render_report(facts: dict[str, Any], percent_digits: int, max_focus: int, max_alerts: int) -> str:
    """Render the fixed V1 report layout; this function does not calculate metrics."""
    lines = [
        "# 量化私募周度跟踪报告｜{}".format(facts["as_of_date"]),
        "",
        "> 数据截止：{}  ".format(facts["as_of_date"]),
        "> 上期：%s  " % (facts["previous_as_of_date"] or "无"),
        "> 样本字段覆盖：{}  ".format(_pct(facts["data_quality"]["sample_coverage"], percent_digits)),
        "> 分析版本：{}".format(facts["analytics_version"]),
        "",
        "## 1. 本周结论",
        "",
    ]
    lines.extend(_conclusion_lines(facts, percent_digits))
    lines.extend(["", "## 2. 市场与基准表现", ""])
    lines.extend(_market_table(facts["market"]["benchmarks"], percent_digits))
    lines.extend(["", "### V2A 风格环境", ""])
    lines.extend(_style_conclusion_table(
        facts["market"]["style"]["summary"]["category_conclusions"]))
    lines.extend([""])
    lines.extend(_v2_style_table(facts["market"]["style"]["proxies"], percent_digits))
    lines.extend(["", "### 近12周风格热力图", ""])
    lines.extend(_style_heatmap(
        facts["market"]["style"]["proxies"],
        facts["market"]["style"]["summary"]["heatmap_weeks"], percent_digits))
    lines.extend([
        "",
        "> 说明：V2A 以价格指数收益差构造风格代理；不推断成交、广度、个股因子暴露或 Barra 因子收益。",
        "",
        "## 3. 指增市场概览",
        "",
        "| 策略 | 基准收益 | 管理人×策略周收益中位数 | 超额中位数 | P25 | P75 | 分化度 | 正超额比例 | 样本数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for item in _ordered_strategies(facts["strategy_summary"]):
        excess = item["excess_return"]
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            _cell(item["strategy_label"]), _pct(item["benchmark_return"], percent_digits),
            _pct(item["manager_strategy_return"]["median"], percent_digits),
            _pct(excess["median"], percent_digits), _pct(excess["p25"], percent_digits),
            _pct(excess["p75"], percent_digits), _pct(excess["dispersion_p75_p25"], percent_digits),
            _pct(item["positive_excess_ratio"], percent_digits), item["sample_size"],
        ))
    lines.extend(["", "## 4. 近期趋势", ""])
    lines.extend(_trend_table(facts["strategy_trend"], percent_digits))
    if facts["alpha_heatmap"]["enabled"]:
        lines.extend(["", "### 近12周 Alpha 热力图", ""])
        lines.extend(_alpha_median_heatmap(facts["alpha_heatmap"], percent_digits))
        lines.extend(["", "### 近12周正超额管理人比例", ""])
        lines.extend(_alpha_positive_ratio_heatmap(facts["alpha_heatmap"], percent_digits))
    lines.extend(["", "## 5. 管理人变化", "", "### 本周表现靠前", ""])
    lines.extend(_ranked_table(_all_ranked(facts), percent_digits, reverse=True))
    lines.extend(["", "### 本周表现靠后", ""])
    lines.extend(_ranked_table(_all_ranked(facts), percent_digits, reverse=False))
    if facts["size_analysis"]["enabled"]:
        lines.extend(["", "## 6. 管理规模分组", ""])
        lines.extend(_size_group_summary_table(facts["size_analysis"], percent_digits))
        lines.extend(["", "### 管理规模分组明细", ""])
        lines.extend(_size_group_detail_table(facts["size_analysis"], percent_digits))
    lines.extend(["", "## 7. 重点管理人 Watchlist", ""])
    lines.extend(_watchlist(facts["focus_managers"][:max_focus], percent_digits))
    lines.extend(["", "## 8. 本周异常与观察名单", ""])
    lines.extend(_alerts(facts["alerts"], max_alerts))
    lines.extend(["", "## 9. 数据质量与口径", ""])
    quality = facts["data_quality"]
    lines.extend([
        "- 缺失策略：{}".format(_text_list(quality["missing_strategies"])),
        "- 样本不足：{}".format(_text_list(quality["insufficient_samples"])),
        "- 管理规模字段覆盖：{}；未知规模观测：{}。".format(
            _pct(quality["size_category_coverage"], percent_digits),
            quality["unknown_size_observation_count"]),
        "- 超额口径：{}".format(facts["methodology"]["excess_definition"]),
        "- 近4/12周超额聚合：{}".format(facts["methodology"]["rolling_excess_aggregation"]),
        "- 指增 Alpha 热力图：{}；{}。".format(
            facts["methodology"]["alpha_heatmap_grain"],
            facts["methodology"]["alpha_heatmap_metric"]),
        "- 口径区别：近4/12周是单个管理人周超额的滚动累计；Alpha 热力图是每个实际报告周重新计算管理人横截面，不跨周累计。",
        "- 基准实际取值日期：见 `report_facts.json` 的 `market.benchmarks`。",
        "- V2A 风格口径：{}".format(facts["methodology"]["style_return_definition"]),
        "- V2A 风格数据：{}/{} 个代理本周可用；实际取值日期见 `market.style`。".format(
            facts["market"]["style"]["summary"]["available_proxy_count"],
            facts["market"]["style"]["summary"]["configured_proxy_count"]),
        "- 其他 warning：{}".format(_text_list(quality["warnings"])),
        "",
    ])
    return "\n".join(lines)


def _conclusion_lines(facts: dict[str, Any], digits: int) -> list[str]:
    summaries = _ordered_strategies(facts["strategy_summary"])
    if not summaries:
        return ["| 策略 | 超额中位数 | 正超额比例 | 样本数 | 状态 |", "|---|---:|---:|---:|---|"]
    lines = [
        "| 策略 | 超额中位数 | 正超额比例 | 样本数 | 状态 |",
        "|---|---:|---:|---:|---|",
    ]
    for item in summaries:
        if item["data_quality"]["status"] == "insufficient_sample":
            status = "样本不足，仅作描述性展示"
        else:
            status = "正常"
        lines.append("| {} | {} | {} | {} | {} |".format(
            _cell(item["strategy_label"]), _pct(item["excess_return"]["median"], digits),
            _pct(item["positive_excess_ratio"], digits), item["sample_size"], status,
        ))
    lines.extend([
        "",
        "| 市场风格代理 | 本周结论 |",
        "|---|---|",
        "| 综合判断 | {} |".format(facts["market"]["environment_label"]),
    ])
    style_headline = facts["market"].get("style", {}).get("summary", {}).get("headline")
    if style_headline:
        lines.append(f"| V2A 风格 | {_cell(style_headline)} |")
    alpha_headline = facts.get("alpha_heatmap", {}).get("summary", {}).get("headline")
    if facts.get("alpha_heatmap", {}).get("enabled") and alpha_headline:
        lines.append(f"| 指增 Alpha | {_cell(alpha_headline)} |")
    size_headline = facts.get("size_analysis", {}).get("summary", {}).get("headline")
    if facts.get("size_analysis", {}).get("enabled") and size_headline:
        lines.append(f"| 管理规模 | {_cell(size_headline)} |")
    return lines


def _market_table(items: list[dict[str, Any]], digits: int) -> list[str]:
    lines = ["| 基准 | 本周 | 近4周 | 近12周 | 实际取值日 |", "|---|---:|---:|---:|---|"]
    for item in _ordered_benchmarks(items):
        lines.append("| {} | {} | {} | {} | {} |".format(
            _cell(item["benchmark_label"]), _pct(item["weekly_return"], digits),
            _pct(item["rolling"].get("weeks_4", {}).get("return"), digits),
            _pct(item["rolling"].get("weeks_12", {}).get("return"), digits),
            item["as_of_nav_date"] or "—",
        ))
    return lines


def _style_table(items: list[dict[str, Any]], digits: int) -> list[str]:
    lines = ["| 代理 | 本周差值 | 状态 |", "|---|---:|---|"]
    for item in items:
        lines.append("| {} | {} | {} |".format(
            _cell(item["label"]), _pct(item["weekly_difference"], digits), item["status"]))
    return lines


def _v2_style_table(items: list[dict[str, Any]], digits: int) -> list[str]:
    lines = [
        "| 风格代理 | 本周差值 | 近4周 | 近12周 | 本周状态 | 连续同向 | 12周切换 |",
        "|---|---:|---:|---:|---|---:|---:|",
    ]
    for item in items:
        weekly = item["weekly"]
        rolling = item["rolling"]
        status = weekly.get("direction")
        if weekly["status"] != "ok":
            status = "数据不完整：{}".format(weekly.get("reason", "未知原因"))
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            _cell(item["label"]), _pct(weekly.get("spread"), digits),
            _pct(rolling.get("weeks_4", {}).get("spread"), digits),
            _pct(rolling.get("weeks_12", {}).get("spread"), digits),
            _cell(status or "—"), item["stability"]["current_streak_weeks"],
            item["stability"]["switch_count"],
        ))
    return lines


def _style_conclusion_table(items: list[dict[str, Any]]) -> list[str]:
    """Render deterministic V2A category conclusions before the detailed proxy table."""
    lines = [
        "#### 风格结论（V2A）",
        "",
        "| 维度 | 本周 | 近4周 | 近12周 | 结论 |",
        "|---|---|---|---|---|",
    ]
    for item in items:
        lines.append("| {} | {} | {} | {} | {} |".format(
            _cell(item["category"]), _cell(item["weekly"]["label"]),
            _cell(item["weeks_4"]["label"]), _cell(item["weeks_12"]["label"]),
            _cell(item["trend_comment"]),
        ))
    lines.extend([
        "",
        "> 仅当同一维度全部配置代理均有数据且同向时才给出占优/不占优；“短线反转”仅表示"
        "本周与近4周收益差方向相反，不代表趋势已确认。",
    ])
    return lines


def _style_heatmap(items: list[dict[str, Any]], max_weeks: int, digits: int) -> list[str]:
    all_dates = []
    for item in items:
        for point in item["history"]:
            if point["as_of_date"] not in all_dates:
                all_dates.append(point["as_of_date"])
    dates = sorted(all_dates)[-max_weeks:]
    if not dates:
        return ["风格历史不足。"]
    lines = ["| 风格代理 | {} |".format(" | ".join(item[5:] for item in dates))]
    lines.append("|---|{}|".format("|".join("---:" for _ in dates)))
    for item in items:
        points = {point["as_of_date"]: point for point in item["history"]}
        cells = [_style_heatmap_cell(points.get(item_date), digits) for item_date in dates]
        lines.append("| {} | {} |".format(_cell(item["label"]), " | ".join(cells)))
    lines.append("")
    lines.append(
        "> `↑` 为多头腿相对占优，`↓` 为对照腿相对占优，`≈` 为中性区间，"
        "`—` 为数据不完整。")
    return lines


def _style_heatmap_cell(point: Any, digits: int) -> str:
    if not point or point.get("spread") is None:
        return "—"
    value = float(point["spread"])
    sign = point.get("sign")
    if sign is None:
        sign = 1 if value > 0 else (-1 if value < 0 else 0)
    if sign > 0:
        return f"↑{_pct(value, digits)}"
    if sign < 0:
        return f"↓{_pct(abs(value), digits)}"
    return f"≈{_pct(abs(value), digits)}"


def _trend_table(items: list[dict[str, Any]], digits: int) -> list[str]:
    lines = ["| 策略 | 近4周超额中位数 | 近4周正超额比例 | 本周较上周变化 |", "|---|---:|---:|---:|"]
    for item in _ordered_strategies(items):
        four = item["rolling"].get("weeks_4", {})
        lines.append("| {} | {} | {} | {} |".format(
            _cell(item["strategy_label"]), _pct(four.get("median_excess"), digits),
            _pct(four.get("positive_ratio"), digits),
            _pct(item["comparison"].get("median_excess_change"), digits),
        ))
    return lines


def _alpha_median_heatmap(alpha_heatmap: dict[str, Any], digits: int) -> list[str]:
    dates = alpha_heatmap["weeks"]
    if not dates:
        return ["指增 Alpha 历史不足。"]
    lines = ["| 策略 | {} | 当前状态 |".format(" | ".join(day[5:] for day in dates))]
    lines.append("|---|{}|---|".format("|".join("---:" for _ in dates)))
    for strategy in _ordered_strategies(alpha_heatmap["strategies"]):
        points = {point["as_of_date"]: point for point in strategy["history"]}
        cells = [_alpha_median_cell(points.get(day), digits) for day in dates]
        lines.append("| {} | {} | {} |".format(
            _cell(strategy["strategy_label"]), " | ".join(cells),
            _cell(strategy["trend"]["label"])))
    lines.extend([
        "",
        "> `↑`/`↓` 表示当周管理人超额中位数方向，`≈` 表示绝对值不超过0.05%，"
        "`—` 表示样本不足或数据缺失。",
    ])
    return lines


def _alpha_positive_ratio_heatmap(alpha_heatmap: dict[str, Any], digits: int) -> list[str]:
    dates = alpha_heatmap["weeks"]
    if not dates:
        return ["指增正超额管理人比例历史不足。"]
    lines = ["| 策略 | {} |".format(" | ".join(day[5:] for day in dates))]
    lines.append("|---|{}|".format("|".join("---:" for _ in dates)))
    for strategy in _ordered_strategies(alpha_heatmap["strategies"]):
        points = {point["as_of_date"]: point for point in strategy["history"]}
        cells = [_alpha_ratio_cell(points.get(day), digits) for day in dates]
        lines.append("| {} | {} |".format(
            _cell(strategy["strategy_label"]), " | ".join(cells)))
    lines.extend([
        "",
        "> 比例分母为当周该策略 `weekly_excess` 有效的管理人数量；样本不足显示 `—`，缺失值不按 0 处理。",
    ])
    return lines


def _alpha_median_cell(point: Any, digits: int) -> str:
    if not point or point["status"] == "insufficient_sample":
        return "—"
    value = point["median_weekly_excess"]
    if value is None:
        return "—"
    symbol = {"positive": "↑", "negative": "↓", "neutral": "≈"}[point["status"]]
    return symbol + _pct(abs(float(value)), digits)


def _alpha_ratio_cell(point: Any, digits: int) -> str:
    if not point or point["status"] == "insufficient_sample":
        return "—"
    return _pct(point["positive_excess_ratio"], digits)


def _size_group_summary_table(size_analysis: dict[str, Any], digits: int) -> list[str]:
    groups = size_analysis["groups"]
    labels = [group["group_label"] for group in groups]
    lines = [
        "| 策略 | {} | 规模观察 |".format(
            " | ".join(f"{_cell(label)}超额中位数" for label in labels)),
        "|---|{}|---|".format("|".join("---:" for _ in groups)),
    ]
    for strategy in _ordered_strategies(size_analysis["strategies"]):
        facts_by_key = {group["group_key"]: group for group in strategy["groups"]}
        cells = [
            _size_group_summary_cell(facts_by_key[group["group_key"]], digits)
            for group in groups
        ]
        lines.append("| {} | {} | {} |".format(
            _cell(strategy["strategy_label"]), " | ".join(cells),
            _cell(strategy["effect_summary"]["headline"])))
    return lines


def _size_group_detail_table(size_analysis: dict[str, Any], digits: int) -> list[str]:
    lines = [
        "| 策略 | 规模组 | 样本数 | 超额中位数 | P25 | P75 | 正超额比例 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    configured_keys = [group["group_key"] for group in size_analysis["groups"]]
    for strategy in _ordered_strategies(size_analysis["strategies"]):
        facts_by_key = {group["group_key"]: group for group in strategy["groups"]}
        for group_key in configured_keys:
            group = facts_by_key[group_key]
            if group["status"] == "insufficient_sample":
                median, p25, p75, ratio = (
                    f"样本不足（n={group['sample_size']}）", "—", "—", "—")
            else:
                median = _pct(group["weekly_excess_median"], digits)
                p25 = _pct(group["weekly_excess_p25"], digits)
                p75 = _pct(group["weekly_excess_p75"], digits)
                ratio = _pct(group["positive_excess_ratio"], digits)
            lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                _cell(strategy["strategy_label"]), _cell(group["group_label"]),
                group["sample_size"], median, p25, p75, ratio))
    return lines


def _size_group_summary_cell(group: dict[str, Any], digits: int) -> str:
    if group["status"] == "insufficient_sample":
        return "样本不足（n={}）".format(group["sample_size"])
    return _pct(group["weekly_excess_median"], digits)


def _all_ranked(facts: dict[str, Any]) -> list[dict[str, Any]]:
    return [record for summary in facts["strategy_summary"] for record in summary["ranked_managers"]]


def _ordered_strategies(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {key: index for index, key in enumerate(STRATEGY_TEMPLATE_ORDER)}
    return sorted(items, key=lambda item: (
        order.get(item["strategy_key"], len(order)),
        item["strategy_key"],
    ))


def _ordered_benchmarks(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {key: index for index, key in enumerate(BENCHMARK_TEMPLATE_ORDER)}
    return sorted(items, key=lambda item: (
        order.get(item["benchmark_key"], len(order)),
        item["benchmark_key"],
    ))


def _strategy_sort_key(item: dict[str, Any]):
    order = {key: index for index, key in enumerate(STRATEGY_TEMPLATE_ORDER)}
    strategy_key = item.get("strategy_key", "")
    return order.get(strategy_key, len(order)), strategy_key


def _ordered_by_strategy(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = list(enumerate(items))
    return [item for _, item in sorted(indexed, key=lambda pair: (
        _strategy_sort_key(pair[1]), pair[0],
    ))]


def _ranked_table(items: list[dict[str, Any]], digits: int, reverse: bool) -> list[str]:
    def percentile_sort_value(item):
        value = item["peer_percentile"]
        if value is None:
            return 0.0
        return -value if reverse else value

    performance_ordered = sorted(items, key=lambda item: (
        item["peer_percentile"] is None,
        percentile_sort_value(item),
        item["manager_name"], item["strategy_key"],
    ))[:10]
    ordered = _ordered_by_strategy(performance_ordered)
    lines = ["| 管理人 | 策略 | 周超额 | 同类百分位 | 排名变化 |", "|---|---|---:|---:|---:|"]
    for item in ordered:
        lines.append("| {} | {} | {} | {} | {} |".format(
            _cell(item["manager_name"]), _cell(item["strategy_label"]),
            _pct(item["weekly_excess"], digits), _pct(item["peer_percentile"], digits),
            _signed_int(item["rank_change"]),
        ))
    return lines


def _watchlist(cards: list[dict[str, Any]], digits: int) -> list[str]:
    if not cards:
        return ["未配置重点管理人。"]
    lines = []
    manager_order = {}
    for card in cards:
        manager_order.setdefault(card["manager_name"], len(manager_order))
    for card in sorted(cards, key=lambda item: (
            manager_order[item["manager_name"]], _strategy_sort_key(item))):
        if card.get("status") == "missing_manager":
            lines.extend(["### {}".format(_cell(card["manager_name"])), "", "- 状态：配置的管理人未在数据库中找到。", ""])
            continue
        if card.get("status") == "missing_current_observation":
            lines.extend([
                "### {}｜{}".format(_cell(card["manager_name"]), _cell(card["strategy_label"])),
                "", "- 状态：本报告截止日没有该管理人 × 策略的有效观测。", "",
            ])
            continue
        current = card["current"]
        recent = card["recent"]
        comparison = card["comparison"]
        lines.extend([
            "### {}｜{}".format(_cell(card["manager_name"]), _cell(card["strategy_label"])),
            "",
            "- 本周：周收益 {}，周超额 {}，同类 {}/{}，百分位 {}。".format(
                _pct(current["manager_strategy_return"], digits), _pct(current["excess_return"], digits),
                current["rank"] or "—", current["rank_total"] or "—",
                _pct(current["peer_percentile"], digits)),
            "- 近期：近4周累计超额 {}，正超额 {}/{}，当前超额回撤 {}。".format(
                _pct(recent["weeks_4_cumulative_excess"], digits),
                recent["weeks_4_positive_count"] if recent["weeks_4_positive_count"] is not None else "—",
                recent["weeks_4_observation_count"],
                _pct(recent["current_excess_drawdown"], digits)),
            "- 变化：排名较上周 {}，前周超额 {}。".format(
                _signed_int(comparison["rank_change"]), _pct(comparison["previous_excess"], digits)),
            f"- 状态：{_watch_status(card)}。",
            "",
        ])
    return lines


def _alerts(alerts: list[dict[str, Any]], max_alerts: int) -> list[str]:
    max_per_severity = max(1, max_alerts // 2)
    negative = _ordered_by_strategy(
        [item for item in alerts if item["severity"] == "negative"][:max_per_severity])
    positive = _ordered_by_strategy(
        [item for item in alerts if item["severity"] == "positive"][:max_per_severity])
    lines = ["### 负面观察", ""]
    lines.extend(_alert_lines(negative) or ["- 无。"])
    lines.extend(["", "### 状态改善", ""])
    lines.extend(_alert_lines(positive) or ["- 无。"])
    return lines


def _alert_lines(alerts: Iterable[dict[str, Any]]) -> list[str]:
    return ["- **{}｜{}**：{}。".format(
        _cell(item["manager_name"]), _cell(item["strategy_label"]),
        "；".join(item["message_templates"]),
    ) for item in alerts]


def _watch_status(card: dict[str, Any]) -> str:
    if not card["alerts"]:
        return "暂未触发异常"
    messages = []
    for alert in card["alerts"]:
        messages.extend(alert["message_templates"])
    return "；".join(messages)


def _pct(value: Any, digits: int) -> str:
    return "—" if value is None else f"{float(value) * 100:.{digits}f}%"


def _signed_int(value: Any) -> str:
    if value is None:
        return "—"
    return f"{int(value):+d}"


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _text_list(values: list[str]) -> str:
    return "无" if not values else "；".join(values)
