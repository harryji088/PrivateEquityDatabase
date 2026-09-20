from datetime import date

from analytics.anomaly_detection import detect_anomalies
from analytics.schemas import WeeklyObservation


def _config():
    return {"report": {"min_sample_size": 5}, "anomalies": {
        "negative_weekly_percentile": 0.10, "positive_weekly_percentile": 0.90,
        "negative_rank_change_percentile_points": 25,
        "consecutive_negative_weeks": 3, "consecutive_positive_weeks": 3,
        "weekly_excess_sigma": 2.0, "min_history_weeks_for_drawdown": 8,
        "drawdown_recovery_min": 0.01,
    }}


def _history(manager_id, name, drawdowns):
    result = {}
    for index, drawdown in enumerate(drawdowns):
        item_date = f"2026-01-{index + 1:02d}"
        result[item_date] = WeeklyObservation(
            as_of_date=date.fromisoformat(item_date), week_label=item_date,
            manager_id=manager_id, manager_name=name, strategy_key="index_500",
            strategy_label="500指增", weekly_return=-0.01, weekly_excess=-0.01,
            ytd_return=None, ytd_excess=None, ytd_excess_drawdown=drawdown,
            source_row_id=str(index),
        )
    return result


def test_anomalies_keep_positive_and_negative_signals_separate_and_new_high_is_not_recovery():
    records = []
    histories = {}
    for manager_id, excess in enumerate((-0.05, -0.01, 0.0, 0.01, 0.02), start=1):
        name = "测试管理人" if manager_id == 1 else f"同类{manager_id}"
        histories[(manager_id, "index_500")] = _history(manager_id, name, [-0.03, -0.02, 0.0])
        records.append({
            "manager_id": manager_id, "manager_name": name, "strategy_key": "index_500",
            "weekly_excess": excess, "peer_percentile": 0.0,
            "consecutive_negative_weeks": 3 if manager_id == 1 else 0,
            "consecutive_positive_weeks": 0, "peer_percentile_change": -0.4 if manager_id == 1 else None,
            "rank_change": -4 if manager_id == 1 else None,
            "rolling": {"weeks_4": {"cumulative_excess": None}},
            "ytd_excess_drawdown": 0.0,
        })
    universe = {
        "histories": histories,
        "strategy_summary": [{
            "strategy_key": "index_500", "strategy_label": "500指增", "sample_size": 5,
            "excess_return": {"mean": 0.0, "std": 0.01},
            "rolling": {"weeks_4": {"sample_size": 0, "p10": None, "p90": None}},
            "ranked_managers": records,
        }],
    }
    alerts = detect_anomalies(
        universe, [], "2026-01-03", _config(), {"focus_managers": []})
    target = [item for item in alerts if item["manager_name"] == "测试管理人"]
    assert len(target) == 1
    assert target[0]["severity"] == "negative"
    assert target[0]["strategy_label"] == "500指增"
    assert "CONSECUTIVE_NEGATIVE_EXCESS" in target[0]["codes"]
    assert "EXCESS_DRAWDOWN_RECOVERY" not in target[0]["codes"]


def _recovery_alert_codes(drawdowns):
    records = []
    histories = {}
    for manager_id in range(1, 6):
        name = f"管理人{manager_id}"
        histories[(manager_id, "index_500")] = _history(manager_id, name, drawdowns)
        records.append({
            "manager_id": manager_id, "manager_name": name, "strategy_key": "index_500",
            "weekly_excess": 0.001 * manager_id, "peer_percentile": 0.5,
            "consecutive_negative_weeks": 0, "consecutive_positive_weeks": 0,
            "peer_percentile_change": None, "rank_change": None,
            "rolling": {"weeks_4": {"cumulative_excess": None}},
            "ytd_excess_drawdown": drawdowns[-1],
        })
    universe = {
        "histories": histories,
        "strategy_summary": [{
            "strategy_key": "index_500", "strategy_label": "500指增", "sample_size": 5,
            "excess_return": {"mean": 0.003, "std": 0.002},
            "rolling": {"weeks_4": {"sample_size": 0, "p10": None, "p90": None}},
            "ranked_managers": records,
        }],
    }
    as_of = f"2026-01-{len(drawdowns):02d}"
    alerts = detect_anomalies(
        universe, [], as_of, _config(), {"focus_managers": []})
    return [code for item in alerts for code in item["codes"]]


def test_drawdown_recovery_requires_current_improvement_and_only_fires_on_threshold_crossing():
    assert "EXCESS_DRAWDOWN_RECOVERY" in _recovery_alert_codes(
        [-0.03, -0.025, -0.015])
    assert "EXCESS_DRAWDOWN_RECOVERY" not in _recovery_alert_codes(
        [-0.03, -0.015, -0.02])
    assert "EXCESS_DRAWDOWN_RECOVERY" not in _recovery_alert_codes(
        [-0.03, -0.025, -0.015, -0.01])


def test_rolling_tail_alert_requires_configured_minimum_sample():
    records = []
    histories = {}
    for manager_id in range(1, 6):
        name = f"管理人{manager_id}"
        histories[(manager_id, "index_500")] = _history(manager_id, name, [None])
        records.append({
            "manager_id": manager_id, "manager_name": name, "strategy_key": "index_500",
            "weekly_excess": 0.001 * manager_id, "peer_percentile": 0.5,
            "consecutive_negative_weeks": 0, "consecutive_positive_weeks": 0,
            "peer_percentile_change": None, "rank_change": None,
            "rolling": {"weeks_4": {
                "cumulative_excess": -0.02 if manager_id == 1 else (
                    0.02 if manager_id == 2 else None)}},
            "ytd_excess_drawdown": None,
        })
    universe = {
        "histories": histories,
        "strategy_summary": [{
            "strategy_key": "index_500", "strategy_label": "500指增", "sample_size": 5,
            "excess_return": {"mean": 0.003, "std": 0.002},
            "rolling": {"weeks_4": {
                "sample_size": 2, "p10": -0.016, "p90": 0.016}},
            "ranked_managers": records,
        }],
    }
    alerts = detect_anomalies(
        universe, [], "2026-01-01", _config(), {"focus_managers": []})
    codes = [code for item in alerts for code in item["codes"]]
    assert "WEEKS_4_EXCESS_BOTTOM_DECILE" not in codes
    assert "WEEKS_4_EXCESS_TOP_DECILE" not in codes
