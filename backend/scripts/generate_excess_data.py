"""
Generate excess return DATA for dashboard.html.
Cumulative excess NAV = 1.0 + ytd_excess (same framework as absolute returns).
Only 5 指增 strategies have excess data.
"""
import sqlite3
import json

DB_PATH = "/Users/harryji/Documents/trae_projects/CC/cc_data.sqlite3"

STRATEGY_CN = {
    "index_500": "500指增", "index_1000": "1000指增", "index_300": "300指增",
    "index_2000": "2000指增", "index_a500": "A500指增",
    "stock_long": "量化选股", "market_neutral": "市场中性",
}

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get all weeks
    cur.execute("SELECT DISTINCT week_label FROM weekly_performances ORDER BY week_label")
    week_labels = [r[0] for r in cur.fetchall()]
    print(f"Weeks: {len(week_labels)}")

    # Get all funds that have ANY excess data
    cur.execute("""
        SELECT f.id, f.name, fc.name as company, f.strategy_type, wp.size_category
        FROM weekly_performances wp
        JOIN funds f ON f.id = wp.fund_id
        JOIN fund_companies fc ON fc.id = f.company_id
        WHERE wp.ytd_excess IS NOT NULL
        GROUP BY f.id
        ORDER BY f.strategy_type, fc.name
    """)
    funds_with_excess = cur.fetchall()
    print(f"Funds with excess data: {len(funds_with_excess)}")

    # Build fund-level cumulative excess NAV (1.0 + ytd_excess)
    funds_data = []
    for fid, fname, company, strategy, size_cat in funds_with_excess:
        cur.execute("""
            SELECT week_label, ytd_excess FROM weekly_performances
            WHERE fund_id = ? AND ytd_excess IS NOT NULL
            ORDER BY record_date
        """, (fid,))
        excess_map = {r[0]: r[1] for r in cur.fetchall()}

        navs = []
        for wl in week_labels:
            ex = excess_map.get(wl)
            if ex is not None:
                navs.append(round(1.0 + ex, 6))
            else:
                navs.append(None)

        strategy_cn = STRATEGY_CN.get(strategy, strategy)
        funds_data.append({
            "company": company,
            "strategy": strategy_cn,
            "size": size_cat,
            "navs": navs,
        })

    # Build strategy-level average excess NAVs
    strategy_navs = {}
    strategy_sizes = {}
    for s_key, s_cn in STRATEGY_CN.items():
        # Only include 指增 strategies that have excess
        if s_key in ("stock_long", "market_neutral"):
            continue

        cur.execute("""
            SELECT f.id, f.name, fc.name as company
            FROM weekly_performances wp
            JOIN funds f ON f.id = wp.fund_id
            JOIN fund_companies fc ON fc.id = f.company_id
            WHERE f.strategy_type = ? AND wp.ytd_excess IS NOT NULL
            GROUP BY f.id
        """, (s_key,))
        strat_funds = cur.fetchall()

        if not strat_funds:
            continue

        # Collect all NAVs per week
        week_navs = {wl: [] for wl in week_labels}
        size_set = set()
        for fid, fname, company in strat_funds:
            cur.execute("""
                SELECT week_label, ytd_excess, size_category FROM weekly_performances
                WHERE fund_id = ? AND ytd_excess IS NOT NULL
                ORDER BY record_date
            """, (fid,))
            for wl, ytd_ex, sz in cur.fetchall():
                week_navs[wl].append(1.0 + ytd_ex)
                if sz:
                    size_set.add(sz)

        avg_navs = []
        for wl in week_labels:
            vals = week_navs[wl]
            if vals:
                avg_navs.append(round(sum(vals) / len(vals), 6))
            else:
                avg_navs.append(None)

        strategy_navs[s_cn] = avg_navs
        strategy_sizes[s_cn] = sorted(size_set, key=lambda x: (
            {"100亿以上": 0, "50~100亿": 1, "20~50亿": 2, "10~20亿": 3, "5~10亿": 4, "0~5亿": 5}.get(x, 99)
        ))

    # Build dates list (record_date from DB)
    cur.execute("SELECT DISTINCT record_date FROM weekly_performances ORDER BY record_date")
    dates = [r[0] for r in cur.fetchall()]

    # Build weekLabels, weekInfo, weeklyData (for weekly ranking table)
    week_labels_sorted = sorted(week_labels)
    week_info = {}
    weekly_data = {}
    for wl in week_labels_sorted:
        # Extract date range info from week_label format "0105-0109"
        parts = wl.split("-")
        if len(parts) == 2:
            start_mmdd = parts[0][:2] + "/" + parts[0][2:]
            end_mmdd = parts[1][:2] + "/" + parts[1][2:]
            week_info[wl] = end_mmdd
        else:
            week_info[wl] = wl

        cur.execute("""
            SELECT fc.name, f.strategy_type, wp.size_category,
                   wp.weekly_excess, wp.ytd_excess
            FROM weekly_performances wp
            JOIN funds f ON f.id = wp.fund_id
            JOIN fund_companies fc ON fc.id = f.company_id
            WHERE wp.week_label = ? AND wp.weekly_excess IS NOT NULL
            ORDER BY wp.weekly_excess DESC
        """, (wl,))
        week_records = []
        for company, strategy, size_cat, wk_ex, ytd_ex in cur.fetchall():
            strategy_cn = STRATEGY_CN.get(strategy, strategy)
            week_records.append({
                "company": company,
                "strategy": strategy_cn,
                "size": size_cat,
                "weekly_return": round(wk_ex, 6),   # weekly excess as "return"
                "ytd_return": round(ytd_ex, 6),     # ytd excess as "ytd_return"
            })
        weekly_data[wl] = week_records

    result = {
        "dates": dates,
        "weekLabels": week_labels_sorted,
        "weekInfo": week_info,
        "weeklyData": weekly_data,
        "funds": funds_data,
        "avgNavs": strategy_navs,
        "strategySizes": strategy_sizes,
    }

    # Output as JS
    js = "var EXCESS_DATA = " + json.dumps(result, ensure_ascii=False)
    print(f"\nGenerated EXCESS_DATA: {len(js)} chars")
    print(f"  Funds: {len(funds_data)}")
    print(f"  Strategies: {list(strategy_navs.keys())}")
    print(f"  Dates: {len(dates)}")

    # Write to file for inclusion in HTML
    with open("/Users/harryji/Documents/trae_projects/CC/excess_data.js", "w", encoding="utf-8") as f:
        f.write(js)
    print(f"\nWritten to excess_data.js")

    conn.close()

if __name__ == "__main__":
    main()
