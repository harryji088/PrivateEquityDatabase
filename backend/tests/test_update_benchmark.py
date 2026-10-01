import copy
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import update_benchmark as benchmark  # noqa: E402


def _cache(last_dates=None):
    last_dates = last_dates or {}
    result = {}
    for name in benchmark.INDEX_CODES:
        dates = ["20251231", "20260929"]
        navs = [1.0, 1.2]
        if last_dates.get(name) == "20260930":
            dates.append("20260930")
            navs.append(1.21)
        result[name] = {"dates": dates, "navs": navs}
    return result


def test_update_cache_checks_each_series_instead_of_global_max():
    existing = _cache({"沪深300": "20260930"})
    calls = []

    def fetcher(code, start, end):
        calls.append((code, start, end))
        return {start: 100.0, end: 101.0}

    updated, count = benchmark.update_cache(existing, "20260930", fetcher)

    assert count == len(benchmark.INDEX_CODES) - 1
    assert len(calls) == len(benchmark.INDEX_CODES) - 1
    assert all(item["dates"][-1] == "20260930" for item in updated.values())
    assert existing["中证500"]["dates"][-1] == "20260929"


def test_update_cache_failure_does_not_mutate_input():
    existing = _cache()
    before = copy.deepcopy(existing)

    def fetcher(code, start, end):
        if code == benchmark.INDEX_CODES["中证500"]:
            raise RuntimeError("network failed")
        return {start: 100.0, end: 101.0}

    with pytest.raises(RuntimeError, match="network failed"):
        benchmark.update_cache(existing, "20260930", fetcher)
    assert existing == before


def test_validate_cache_rejects_missing_anchor_and_duplicate_dates():
    data = _cache()
    data["沪深300"] = {"dates": ["20260929"], "navs": [1.2]}
    with pytest.raises(ValueError, match="normalization anchor"):
        benchmark.validate_cache(data)

    data = _cache()
    data["沪深300"] = {
        "dates": ["20251231", "20260929", "20260929"],
        "navs": [1.0, 1.2, 1.2],
    }
    with pytest.raises(ValueError, match="sorted and unique"):
        benchmark.validate_cache(data)
