from analytics.report_renderer import (
    _alerts,
    _alpha_median_heatmap,
    _alpha_positive_ratio_heatmap,
    _conclusion_lines,
    _market_table,
    _ordered_strategies,
    _ranked_table,
    _size_group_detail_table,
    _size_group_summary_table,
    _style_conclusion_table,
    _trend_table,
    _watchlist,
)


def test_bottom_table_keeps_zero_percentile_as_the_worst_record():
    items = [
        {
            "manager_name": "末名", "strategy_key": "index_500", "strategy_label": "500指增",
            "weekly_excess": -0.02, "peer_percentile": 0.0, "rank_change": -2,
        },
        {
            "manager_name": "倒数第二", "strategy_key": "index_500", "strategy_label": "500指增",
            "weekly_excess": -0.01, "peer_percentile": 0.1, "rank_change": -1,
        },
    ]
    lines = _ranked_table(items, 2, reverse=False)
    assert "末名" in lines[2]
    assert "0.00%" in lines[2]


def _strategy_item(strategy_key):
    label = {
        "index_300": "300指增",
        "index_a500": "A500指增",
        "index_500": "500指增",
        "index_1000": "1000指增",
        "index_2000": "2000指增",
    }[strategy_key]
    return {
        "strategy_key": strategy_key,
        "strategy_label": label,
        "sample_size": 10,
        "positive_excess_ratio": 0.6,
        "excess_return": {"median": 0.01},
        "data_quality": {"status": "ok"},
        "rolling": {"weeks_4": {"median_excess": 0.02, "positive_ratio": 0.7}},
        "comparison": {"median_excess_change": 0.001},
    }


def test_summary_tables_use_the_fixed_strategy_and_benchmark_order():
    unordered = [_strategy_item(key) for key in (
        "index_1000", "index_2000", "index_500", "index_a500", "index_300")]
    expected_labels = ["300指增", "A500指增", "500指增", "1000指增", "2000指增"]
    assert [item["strategy_label"] for item in _ordered_strategies(unordered)] == expected_labels

    conclusion = _conclusion_lines({
        "strategy_summary": unordered,
        "market": {"environment_label": "大盘相对占优"},
    }, 2)
    assert conclusion[0] == "| 策略 | 超额中位数 | 正超额比例 | 样本数 | 状态 |"
    assert [line.split("|")[1].strip() for line in conclusion[2:7]] == expected_labels
    assert not any(line.startswith("- ") for line in conclusion)

    conclusion_with_style = _conclusion_lines({
        "strategy_summary": unordered,
        "market": {
            "environment_label": "大盘相对占优",
            "style": {"summary": {"headline": "本周：成长价值：成长相对占优。"}},
        },
    }, 2)
    assert conclusion_with_style[-1] == "| V2A 风格 | 本周：成长价值：成长相对占优。 |"

    trends = _trend_table(unordered, 2)
    assert [line.split("|")[1].strip() for line in trends[2:]] == expected_labels

    benchmarks = [
        {"benchmark_key": key, "benchmark_label": key, "weekly_return": 0.01,
         "rolling": {"weeks_4": {"return": 0.01}, "weeks_12": {"return": 0.01}},
         "as_of_nav_date": "20260109"}
        for key in ("CSI1000", "CSI2000", "CSI500", "A500", "CSI300")
    ]
    market = _market_table(benchmarks, 2)
    assert [line.split("|")[1].strip() for line in market[2:]] == [
        "CSI300", "A500", "CSI500", "CSI1000", "CSI2000",
    ]


def test_style_conclusion_table_explains_signal_agreement_and_short_term_reversal():
    lines = _style_conclusion_table([{
        "category": "成长价值",
        "weekly": {"label": "成长相对占优"},
        "weeks_4": {"label": "价值相对占优"},
        "weeks_12": {"label": "价值相对占优"},
        "trend_comment": "短线反转；近4周与近12周主导方向未变",
    }])

    assert lines[0] == "#### 风格结论（V2A）"
    assert "成长相对占优" in lines[4]
    assert "短线反转" in lines[4]
    assert "不代表趋势已确认" in lines[-1]


def test_management_watchlist_and_alerts_use_the_fixed_strategy_order():
    ranked = [
        {"manager_name": "千", "strategy_key": "index_1000", "strategy_label": "1000指增",
         "weekly_excess": 0.03, "peer_percentile": 0.9, "rank_change": 1},
        {"manager_name": "万", "strategy_key": "index_500", "strategy_label": "500指增",
         "weekly_excess": 0.02, "peer_percentile": 0.8, "rank_change": 1},
        {"manager_name": "三", "strategy_key": "index_300", "strategy_label": "300指增",
         "weekly_excess": 0.01, "peer_percentile": 0.7, "rank_change": 1},
    ]
    management = _ranked_table(ranked, 2, reverse=True)
    assert [line.split("|")[2].strip() for line in management[2:]] == [
        "300指增", "500指增", "1000指增",
    ]

    cards = [
        {"manager_name": "甲", "strategy_key": "index_1000", "strategy_label": "1000指增",
         "status": "missing_current_observation"},
        {"manager_name": "甲", "strategy_key": "index_300", "strategy_label": "300指增",
         "status": "missing_current_observation"},
        {"manager_name": "乙", "strategy_key": "index_a500", "strategy_label": "A500指增",
         "status": "missing_current_observation"},
    ]
    watchlist = _watchlist(cards, 2)
    headings = [line for line in watchlist if line.startswith("###")]
    assert headings == ["### 甲｜300指增", "### 甲｜1000指增", "### 乙｜A500指增"]

    alerts = [
        {"severity": "negative", "manager_name": "甲", "strategy_key": "index_1000",
         "strategy_label": "1000指增", "message_templates": ["测试"]},
        {"severity": "negative", "manager_name": "乙", "strategy_key": "index_500",
         "strategy_label": "500指增", "message_templates": ["测试"]},
        {"severity": "negative", "manager_name": "丙", "strategy_key": "index_300",
         "strategy_label": "300指增", "message_templates": ["测试"]},
    ]
    alert_lines = _alerts(alerts, 6)
    rendered = [line for line in alert_lines if line.startswith("- **")]
    assert [line.split("｜")[1].split("**")[0] for line in rendered] == [
        "300指增", "500指增", "1000指增",
    ]


def test_alpha_tables_only_format_precomputed_facts_and_keep_template_order():
    alpha = {
        "weeks": ["2026-09-04", "2026-09-11"],
        "strategies": [{
            "strategy_key": "index_500", "strategy_label": "500指增",
            "trend": {"state": "mixed", "label": "震荡"},
            "history": [
                {"as_of_date": "2026-09-04", "status": "negative",
                 "median_weekly_excess": 0.01, "positive_excess_ratio": 0.2},
                {"as_of_date": "2026-09-11", "status": "insufficient_sample",
                 "median_weekly_excess": 0.03, "positive_excess_ratio": 1.0},
            ],
        }, {
            "strategy_key": "index_300", "strategy_label": "300指增",
            "trend": {"state": "improving", "label": "改善"},
            "history": [
                {"as_of_date": "2026-09-04", "status": "neutral",
                 "median_weekly_excess": -0.0004, "positive_excess_ratio": 0.5},
                {"as_of_date": "2026-09-11", "status": "positive",
                 "median_weekly_excess": 0.002, "positive_excess_ratio": 0.75},
            ],
        }],
    }
    median_lines = _alpha_median_heatmap(alpha, 2)
    ratio_lines = _alpha_positive_ratio_heatmap(alpha, 2)
    assert "300指增" in median_lines[2]
    assert "≈0.04%" in median_lines[2]
    assert "↓1.00%" in median_lines[3]
    assert median_lines[3].endswith("— | 震荡 |")
    assert "50.00%" in ratio_lines[2]
    assert ratio_lines[3].endswith("20.00% | — |")


def test_size_tables_only_render_precomputed_status_metrics_and_headline():
    size_analysis = {
        "groups": [
            {"group_key": "large", "group_label": "百亿以上"},
            {"group_key": "medium", "group_label": "20~100亿"},
            {"group_key": "small", "group_label": "20亿以下"},
        ],
        "strategies": [{
            "strategy_key": "index_500", "strategy_label": "500指增",
            "effect_summary": {"status": "meaningful", "headline": "预计算规模结论"},
            "groups": [{
                "group_key": "large", "group_label": "百亿以上",
                "sample_size": 2, "status": "insufficient_sample",
                "weekly_excess_median": 0.99, "weekly_excess_p25": 0.98,
                "weekly_excess_p75": 1.0, "positive_excess_ratio": 1.0,
            }, {
                "group_key": "medium", "group_label": "20~100亿",
                "sample_size": 10, "status": "ok",
                "weekly_excess_median": 0.002, "weekly_excess_p25": -0.001,
                "weekly_excess_p75": 0.004, "positive_excess_ratio": 0.6,
            }, {
                "group_key": "small", "group_label": "20亿以下",
                "sample_size": 8, "status": "ok",
                "weekly_excess_median": 0.004, "weekly_excess_p25": 0.001,
                "weekly_excess_p75": 0.006, "positive_excess_ratio": 0.75,
            }],
        }],
    }
    summary = _size_group_summary_table(size_analysis, 2)
    detail = _size_group_detail_table(size_analysis, 2)

    assert "样本不足（n=2）" in summary[2]
    assert "99.00%" not in "\n".join(summary + detail)
    assert "预计算规模结论" in summary[2]
    assert "0.20%" in summary[2]
    assert "75.00%" in detail[-1]
