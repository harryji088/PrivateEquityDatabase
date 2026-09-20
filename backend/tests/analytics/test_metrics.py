from analytics.metrics import (
    consecutive_sign_count,
    percentile_from_rank,
    positive_ratio,
    quantile,
    rank_desc,
    trailing_complete_values,
)


def test_linear_quantile_handles_even_values_and_missing_values():
    values = [None, 0.0, 0.02, 0.04, 0.10]
    assert quantile(values, 0.25) == 0.015
    assert quantile(values, 0.50) == 0.03
    assert quantile(values, 0.75) == 0.055
    assert quantile([], 0.50) is None


def test_positive_ratio_excludes_missing_and_zero_is_not_positive():
    assert positive_ratio([None, -0.01, 0.0, 0.02]) == 1 / 3
    assert positive_ratio([None]) is None


def test_rank_desc_is_stable_for_ties_and_percentiles_are_defined():
    ranked = rank_desc([
        {"manager_name": "Bravo", "value": 0.01},
        {"manager_name": "Alpha", "value": 0.01},
        {"manager_name": "Charlie", "value": -0.01},
    ], "value", "manager_name")
    assert [item["manager_name"] for item in ranked] == ["Alpha", "Bravo", "Charlie"]
    assert [item["rank"] for item in ranked] == [1, 2, 3]
    assert ranked[0]["peer_percentile"] == 1.0
    assert ranked[-1]["peer_percentile"] == 0.0
    assert percentile_from_rank(1, 1) is None


def test_trailing_window_requires_all_dates_and_consecutive_sign_breaks_on_missing():
    dates = ["2026-01-02", "2026-01-09", "2026-01-16", "2026-01-23"]
    assert trailing_complete_values(
        {dates[0]: 0.01, dates[1]: 0.02, dates[2]: -0.01, dates[3]: 0.03},
        dates, dates[-1], 4) == [0.01, 0.02, -0.01, 0.03]
    assert trailing_complete_values(
        {dates[0]: 0.01, dates[2]: -0.01, dates[3]: 0.03}, dates, dates[-1], 4) is None
    assert consecutive_sign_count([0.01, 0.02, None, -0.01], positive=False) == 1
    assert consecutive_sign_count([0.01, 0.02, None, 0.03], positive=True) == 1
