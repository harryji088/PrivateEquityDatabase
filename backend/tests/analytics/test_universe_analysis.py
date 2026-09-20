from datetime import date

from analytics.schemas import WeeklyObservation
from analytics.universe_analysis import analyze_universe


def _observation(day, manager_id, manager_name, excess, weekly_return=None):
    return WeeklyObservation(
        as_of_date=date.fromisoformat(day),
        week_label=day,
        manager_id=manager_id,
        manager_name=manager_name,
        strategy_key="index_500",
        strategy_label="500指增",
        weekly_return=weekly_return if weekly_return is not None else excess,
        weekly_excess=excess,
        ytd_return=None,
        ytd_excess=None,
        ytd_excess_drawdown=None,
        source_row_id=f"{manager_id}-{day}",
    )


def test_rank_change_is_previous_rank_minus_current_rank_and_rolling_requires_full_window():
    dates = ["2026-01-02", "2026-01-09", "2026-01-16", "2026-01-23"]
    observations = []
    # 甲 improves from third to first on the final date; 乙 has a missing week.
    alpha = [0.00, 0.00, 0.00, 0.03]
    beta = [0.03, None, 0.02, 0.01]
    gamma = [0.02, 0.02, 0.02, 0.00]
    for position, day in enumerate(dates):
        for manager_id, manager_name, series in ((1, "甲", alpha), (2, "乙", beta), (3, "丙", gamma)):
            if series[position] is not None:
                observations.append(_observation(day, manager_id, manager_name, series[position]))
    result = analyze_universe(
        observations, dates, dates[-1], dates[-2],
        {"index_500": {"label": "500指增", "benchmark_key": "CSI500"}}, 2, [1, 4])
    summary = result["strategy_summary"][0]
    current = {item["manager_name"]: item for item in summary["ranked_managers"]}
    assert current["甲"]["rank"] == 1
    assert current["甲"]["previous_rank"] == 3
    assert current["甲"]["rank_change"] == 2
    assert current["甲"]["rolling"]["weeks_4"]["cumulative_excess"] == 0.03
    assert current["乙"]["rolling"]["weeks_4"]["cumulative_excess"] is None
    assert summary["excess_return"]["dispersion_p75_p25"] is not None
