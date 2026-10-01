"""
Update benchmark index daily NAV data from CSIndex (中证指数) official API.
Appends new daily data to benchmark_nav.json — existing data is preserved.

Usage:
    python scripts/update_benchmark.py
"""

import json
import math
import os
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BENCHMARK_PATH = PROJECT_ROOT / "benchmark_nav.json"

# Index name → CSIndex index code
INDEX_CODES = {
    "沪深300": "000300",
    "中证500": "000905",
    "中证800": "000906",
    "中证1000": "000852",
    "中证2000": "932000",
    "A500": "000510",
}

CSINDEX_API = "https://www.csindex.com.cn/csindex-home/perf/index-perf"


def fetch_index_data(index_code: str, start_date: str, end_date: str) -> dict[str, float]:
    """Fetch daily close prices from CSIndex API. Returns {date_str: close_price}."""
    url = f"{CSINDEX_API}?indexCode={index_code}&startDate={start_date}&endDate={end_date}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    # CSIndex is expected to be reached directly in this project, regardless
    # of any shell-level proxy used for GitHub.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_error = None
    for _attempt in range(3):
        try:
            with opener.open(req, timeout=30) as resp:
                result = json.loads(resp.read())
            break
        except Exception as exc:
            last_error = exc
    else:
        raise RuntimeError(f"CSIndex request failed after 3 attempts: {last_error}")

    if str(result.get("code")) != "200":
        raise RuntimeError(f"API returned code={result.get('code')}, msg={result.get('msg')}")

    return {item["tradeDate"]: float(item["close"]) for item in result["data"]}


def load_existing() -> dict:
    """Load existing benchmark data."""
    if not BENCHMARK_PATH.exists():
        return {}
    with open(BENCHMARK_PATH) as f:
        return json.load(f)


def validate_cache(data: dict) -> None:
    """Validate every required series before the production cache is replaced."""
    missing = sorted(set(INDEX_CODES) - set(data))
    if missing:
        raise ValueError(f"Missing benchmark series: {', '.join(missing)}")
    for name in INDEX_CODES:
        item = data[name]
        dates = item.get("dates")
        navs = item.get("navs")
        if not dates or not isinstance(dates, list) or not isinstance(navs, list):
            raise ValueError(f"{name}: dates/navs must be non-empty lists")
        if len(dates) != len(navs):
            raise ValueError(f"{name}: dates/navs length mismatch")
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise ValueError(f"{name}: dates must be sorted and unique")
        numeric_navs = [float(value) for value in navs]
        if any(not math.isfinite(value) or value <= 0 for value in numeric_navs):
            raise ValueError(f"{name}: NAVs must be finite and positive")
        if "20251231" not in dates:
            raise ValueError(f"{name}: missing 2025-12-31 normalization anchor")
        anchor = numeric_navs[dates.index("20251231")]
        # Existing caches may carry sub-ppm floating-point drift from the
        # original point-to-NAV conversion.
        if not math.isclose(anchor, 1.0, rel_tol=0, abs_tol=1e-6):
            raise ValueError(f"{name}: 2025-12-31 NAV must equal 1.0, got {anchor}")


def update_cache(existing: dict, end_date: str, fetcher=fetch_index_data) -> tuple[dict, int]:
    """Return a fully validated updated cache without mutating the input."""
    updated = json.loads(json.dumps(existing))
    validate_cache(updated)
    updated_count = 0

    for name, index_code in INDEX_CODES.items():
        existing_data = updated[name]
        latest = existing_data["dates"][-1]
        print(f"\n[{name}] code={index_code}, last={latest}...")
        if latest >= end_date:
            print("  Up to date")
            continue

        new_map = fetcher(index_code, latest, end_date)
        bridge_date = latest
        if bridge_date not in new_map:
            for candidate in reversed(existing_data["dates"]):
                if candidate in new_map:
                    bridge_date = candidate
                    break
            else:
                raise RuntimeError(f"{name}: no bridge date found in API response")

        bridge_close = float(new_map[bridge_date])
        if not math.isfinite(bridge_close) or bridge_close <= 0:
            raise RuntimeError(f"{name}: invalid bridge close {bridge_close}")
        bridge_nav = existing_data["navs"][existing_data["dates"].index(bridge_date)]
        scale = bridge_nav / bridge_close

        existing_dates = set(existing_data["dates"])
        additions = []
        for item_date in sorted(new_map):
            if item_date in existing_dates or item_date <= bridge_date:
                continue
            close = float(new_map[item_date])
            nav = close * scale
            if not math.isfinite(nav) or nav <= 0:
                raise RuntimeError(f"{name}: invalid observation on {item_date}")
            additions.append((item_date, round(nav, 10)))
        existing_data["dates"].extend(item[0] for item in additions)
        existing_data["navs"].extend(item[1] for item in additions)
        print(f"  Added {len(additions)} observations")
        updated_count += 1

    validate_cache(updated)
    return updated, updated_count


def atomic_save(data: dict) -> None:
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=".benchmark_nav-", suffix=".json",
        dir=BENCHMARK_PATH.parent, delete=False)
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, BENCHMARK_PATH)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def main() -> int:
    print("=" * 60)
    print("  基准指数 NAV 更新工具 (CSIndex API)")
    print("=" * 60)

    existing = load_existing()
    print(f"\nLoaded existing data: {len(existing)} indices")
    for k, v in existing.items():
        print(f"  {k}: {len(v['dates'])} dates, last={v['dates'][-1]}")

    if not existing:
        print("ERROR: No existing benchmark data found — run full init first")
        return 1

    today_str = date.today().strftime("%Y%m%d")
    print(f"Today: {today_str}")
    try:
        updated, updated_count = update_cache(existing, today_str)
    except Exception as exc:
        print(f"ERROR: benchmark cache was not changed — {exc}")
        return 1

    atomic_save(updated)
    print(f"\n{'=' * 60}")
    print(f"  Updated {updated_count}/{len(INDEX_CODES)} indices")
    print(f"  Saved to {BENCHMARK_PATH}")

    # Print final state
    print("\nFinal state:")
    for k, v in updated.items():
        print(f"  {k}: {len(v['dates'])} dates, first={v['dates'][0]}, last={v['dates'][-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
