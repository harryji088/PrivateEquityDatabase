"""
Update benchmark index daily NAV data from CSIndex (中证指数) official API.
Appends new daily data to benchmark_nav.json — existing data is preserved.

Usage:
    python scripts/update_benchmark.py
"""

import json
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
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    if result.get("code") != "200":
        raise RuntimeError(f"API returned code={result.get('code')}, msg={result.get('msg')}")

    return {item["tradeDate"]: item["close"] for item in result["data"]}


def load_existing() -> dict:
    """Load existing benchmark data."""
    if not BENCHMARK_PATH.exists():
        return {}
    with open(BENCHMARK_PATH, "r") as f:
        return json.load(f)


def main():
    print("=" * 60)
    print("  基准指数 NAV 更新工具 (CSIndex API)")
    print("=" * 60)

    existing = load_existing()
    print(f"\nLoaded existing data: {len(existing)} indices")
    for k, v in existing.items():
        print(f"  {k}: {len(v['dates'])} dates, last={v['dates'][-1]}")

    if not existing:
        print("ERROR: No existing benchmark data found — run full init first")
        return

    # Find the latest date across all indices
    last_dates = [v["dates"][-1] for v in existing.values() if v["dates"]]
    last_existing = max(last_dates) if last_dates else "20260101"
    print(f"\nLast existing date (max across indices): {last_existing}")

    today_str = date.today().strftime("%Y%m%d")
    print(f"Today: {today_str}")

    if last_existing >= today_str:
        print("✅ Benchmark data is up to date — nothing to fetch")
        return

    updated_count = 0
    for name, index_code in INDEX_CODES.items():
        print(f"\n[{name}] code={index_code}...")

        existing_data = existing.get(name)
        if not existing_data:
            print(f"  SKIP: no existing data for {name}")
            continue

        # Fetch from CSIndex API (from bridge date to today)
        bridge_date = existing_data["dates"][-1]
        try:
            new_map = fetch_index_data(index_code, bridge_date, today_str)
        except Exception as e:
            print(f"  SKIP: fetch failed — {e}")
            continue

        if bridge_date not in new_map:
            print(f"  WARN: bridge date {bridge_date} not in API response")
            # Try earlier dates
            for d in reversed(existing_data["dates"]):
                if d in new_map:
                    bridge_date = d
                    break
            if bridge_date not in new_map:
                print(f"  SKIP: no bridge date found")
                continue

        bridge_close = new_map[bridge_date]
        bridge_nav = existing_data["navs"][existing_data["dates"].index(bridge_date)]
        print(f"  Bridge: {bridge_date} — close={bridge_close:.2f}, nav={bridge_nav:.6f}")

        # Extend NAVs
        extended_dates = list(existing_data["dates"])
        extended_navs = list(existing_data["navs"])
        appended = 0
        cur_date = bridge_date
        cur_close = bridge_close
        cur_nav = bridge_nav

        for d in sorted(new_map.keys()):
            if d <= cur_date:
                continue
            close = new_map[d]
            nav = cur_nav * (close / cur_close)
            extended_dates.append(d)
            extended_navs.append(round(nav, 10))
            appended += 1
            cur_date = d
            cur_close = close
            cur_nav = nav

        existing[name] = {"dates": extended_dates, "navs": extended_navs}
        print(f"  {len(existing_data['dates'])} → {len(extended_dates)} dates (+{appended} new)")
        updated_count += 1

    # Save
    with open(BENCHMARK_PATH, "w") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"\n{'=' * 60}")
    print(f"  Updated {updated_count}/{len(INDEX_CODES)} indices")
    print(f"  Saved to {BENCHMARK_PATH}")

    # Print final state
    print("\nFinal state:")
    for k, v in existing.items():
        print(f"  {k}: {len(v['dates'])} dates, first={v['dates'][0]}, last={v['dates'][-1]}")


if __name__ == "__main__":
    main()
