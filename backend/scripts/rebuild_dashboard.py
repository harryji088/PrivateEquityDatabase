# -*- coding: utf-8 -*-
"""
Clean rebuild of dashboard.html with absolute + excess return tabs.
"""

import sqlite3
import json
import math

import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_ROOT, "cc_data.sqlite3")
BENCHMARK_PATH = os.path.join(PROJECT_ROOT, "benchmark_nav.json")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "dashboard.html")

def norm_size(sz):
    """Normalize size category: 50-100亿 → 50~100亿"""
    if not sz:
        return sz
    return sz.replace("-", "~")

STRATEGY_CN = {
    "index_500": "500指增", "index_1000": "1000指增", "index_300": "300指增",
    "index_2000": "2000指增", "index_a500": "A500指增",
    "stock_long": "量化选股", "market_neutral": "市场中性",
}

SIZE_ORDER_MAP = {"100亿以上": 0, "50~100亿": 1, "20~50亿": 2, "10~20亿": 3, "5~10亿": 4, "0~5亿": 5}

# The abs / excess / excess_dd data sets differ only in: which columns feed
# navs & excesses, how the weekly table is filtered/ordered, which series
# drives within-strategy rank, and whether benchmark data is embedded.
ABS_CFG = {
    "where_funds": "",
    "nav_field": "ytd_return",
    "excess_field": "ytd_excess",
    "weekly_fields": ["weekly_return", "weekly_excess"],
    "weekly_where": "",
    "weekly_order_field": "weekly_return",
    "weekly_record_keys": ["weekly_return", "weekly_excess"],
    "rank_field": "navs",
    "include_bench": True,
}
EXCESS_CFG = {
    "where_funds": "WHERE wp.ytd_excess IS NOT NULL",
    "nav_field": "ytd_excess",
    "excess_field": "ytd_excess",
    "weekly_fields": ["weekly_excess", "ytd_excess"],
    "weekly_where": "AND wp.weekly_excess IS NOT NULL",
    "weekly_order_field": "weekly_excess",
    "weekly_record_keys": ["weekly_return", "ytd_return"],
    "rank_field": "excesses",
    "weekly_excess_series": True,
    "include_bench": False,
}
EXCESS_DD_CFG = {
    "where_funds": "WHERE wp.ytd_excess_drawdown IS NOT NULL",
    "nav_field": "ytd_excess_drawdown",
    "excess_field": "ytd_excess_drawdown",
    "weekly_fields": ["weekly_excess", "ytd_excess_drawdown"],
    "weekly_where": "AND wp.weekly_excess IS NOT NULL",
    "weekly_order_field": "weekly_excess",
    "weekly_record_keys": ["weekly_return", "ytd_return"],
    "rank_field": "excesses",
    "include_bench": False,
}


def build_data_set(cur, cfg):
    """Unified builder for the abs / excess / excess_dd data sets.

    Replaces three ~90%-overloaded functions with one parameterised pass.
    Weekly series are loaded in a SINGLE query (not one per fund), eliminating
    the N+1 pattern. Output is intentionally byte-identical to the previous
    per-dataset functions.
    """
    cur.execute("SELECT DISTINCT record_date, week_label FROM weekly_performances ORDER BY record_date")
    rows = cur.fetchall()
    dates = [r[0] for r in rows]
    week_labels = [r[1] for r in rows]

    week_info = {}
    for wl in week_labels:
        parts = wl.split("-")
        week_info[wl] = (parts[1][:2] + "/" + parts[1][2:]) if len(parts) == 2 else wl

    # Funds matching this dataset's filter
    cur.execute(f"""
        SELECT f.id, f.name, fc.name, f.strategy_type, wp.size_category
        FROM weekly_performances wp
        JOIN funds f ON f.id = wp.fund_id
        JOIN fund_companies fc ON fc.id = f.company_id
        {cfg["where_funds"]}
        GROUP BY f.id
        ORDER BY f.strategy_type, fc.name
    """)
    all_funds = cur.fetchall()

    # Single query for every fund's weekly series (was: one SELECT per fund)
    include_we = cfg.get("weekly_excess_series", False)
    select_fields = []
    for fld in (cfg["nav_field"], cfg["excess_field"]):
        if fld not in select_fields:
            select_fields.append(fld)
    if include_we and "weekly_excess" not in select_fields:
        select_fields.append("weekly_excess")
    cur.execute(
        f"SELECT fund_id, week_label, {', '.join(select_fields)} "
        "FROM weekly_performances ORDER BY fund_id, record_date"
    )
    per_fund = {}
    for row in cur.fetchall():
        per_fund.setdefault(row[0], {})[row[1]] = {
            select_fields[i]: row[2 + i] for i in range(len(select_fields))
        }

    funds_data = []
    for fid, fname, company, strategy, size_cat in all_funds:
        wmap = per_fund.get(fid, {})
        navs, excesses, weekly_excess_series = [], [], []
        for wl in week_labels:
            cell = wmap.get(wl)
            if cell is not None:
                nv = cell.get(cfg["nav_field"])
                ex = cell.get(cfg["excess_field"])
                navs.append(round(1.0 + nv, 6) if nv is not None else None)
                excesses.append(round(ex, 6) if ex is not None else None)
                if include_we:
                    wex = cell.get("weekly_excess")
                    weekly_excess_series.append(round(wex, 6) if wex is not None else None)
            else:
                navs.append(None)
                excesses.append(None)
                if include_we:
                    weekly_excess_series.append(None)
        fund_obj = {
            "company": company,
            "strategy": STRATEGY_CN.get(strategy, strategy),
            "size": norm_size(size_cat),
            "navs": navs,
            "excesses": excesses,
        }
        if include_we:
            fund_obj["weeklyExcess"] = weekly_excess_series
        funds_data.append(fund_obj)

    # Strategy averages + size sets
    strategy_navs, strategy_sizes = {}, {}
    for s_key, s_cn in STRATEGY_CN.items():
        strat_indices = [i for i, f in enumerate(funds_data) if f["strategy"] == s_cn]
        if not strat_indices:
            continue
        week_vals = {wl: [] for wl in week_labels}
        size_set = set()
        for idx in strat_indices:
            f = funds_data[idx]
            size_set.add(f["size"])
            for j, n in enumerate(f["navs"]):
                if n is not None:
                    week_vals[week_labels[j]].append(n)
        strategy_navs[s_cn] = [
            round(sum(week_vals[wl]) / len(week_vals[wl]), 6) if week_vals[wl] else None
            for wl in week_labels
        ]
        strategy_sizes[s_cn] = sorted(size_set, key=lambda x: SIZE_ORDER_MAP.get(x, 99))

    # Weekly ranking table
    weekly_data = {}
    weekly_cols = ", ".join("wp." + f for f in cfg["weekly_fields"])
    for wl in week_labels:
        cur.execute(f"""
            SELECT fc.name, f.strategy_type, wp.size_category, {weekly_cols}
            FROM weekly_performances wp
            JOIN funds f ON f.id = wp.fund_id
            JOIN fund_companies fc ON fc.id = f.company_id
            WHERE wp.week_label = ? {cfg["weekly_where"]}
            ORDER BY wp.{cfg["weekly_order_field"]} DESC
        """, (wl,))
        week_records = []
        for row in cur.fetchall():
            rec = {
                "company": row[0],
                "strategy": STRATEGY_CN.get(row[1], row[1]),
                "size": norm_size(row[2]),
            }
            for key, v in zip(cfg["weekly_record_keys"], row[3:]):
                rec[key] = round(v, 6) if v is not None else None
            week_records.append(rec)
        weekly_data[wl] = week_records

    # Within-strategy rank per fund per week
    num_weeks = len(week_labels)
    rank_field = cfg["rank_field"]
    fund_ranks = [[None] * num_weeks for _ in range(len(funds_data))]
    for s_key, s_cn in STRATEGY_CN.items():
        strat_indices = [i for i, f in enumerate(funds_data) if f["strategy"] == s_cn]
        if not strat_indices:
            continue
        for w_idx in range(num_weeks):
            pairs = [
                (i, funds_data[i][rank_field][w_idx])
                for i in strat_indices
                if funds_data[i][rank_field][w_idx] is not None
            ]
            pairs.sort(key=lambda x: x[1], reverse=True)
            for rank, (i, _) in enumerate(pairs, 1):
                fund_ranks[i][w_idx] = rank
    for i, f in enumerate(funds_data):
        f["ranks"] = fund_ranks[i]

    result = {
        "dates": dates,
        "weekLabels": week_labels,
        "weekInfo": week_info,
        "weeklyData": weekly_data,
        "funds": funds_data,
        "avgNavs": strategy_navs,
        "strategySizes": strategy_sizes,
    }
    if cfg["include_bench"]:
        with open(BENCHMARK_PATH, "r") as bf:
            result["benchData"] = json.load(bf)
        result["strategyBench"] = {
            "量化选股": "中证1000", "市场中性": "沪深300", "500指增": "中证500",
            "1000指增": "中证1000", "300指增": "沪深300", "2000指增": "中证2000", "A500指增": "A500",
        }
    return result


def build_abs_data(cur):
    return build_data_set(cur, ABS_CFG)


def build_excess_data(cur):
    return build_data_set(cur, EXCESS_CFG)


def build_excess_dd_data(cur):
    return build_data_set(cur, EXCESS_DD_CFG)


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    abs_data = build_abs_data(cur)
    excess_data = build_excess_data(cur)
    excess_dd_data = build_excess_dd_data(cur)
    conn.close()

    abs_json = json.dumps(abs_data, ensure_ascii=False)
    exc_json = json.dumps(excess_data, ensure_ascii=False)
    dd_json = json.dumps(excess_dd_data, ensure_ascii=False)

    print(f"ABS_DATA: {len(abs_json)} chars, {len(abs_data['funds'])} funds, {len(abs_data['avgNavs'])} strategies")
    print(f"EXCESS_DATA: {len(exc_json)} chars, {len(excess_data['funds'])} funds, {len(excess_data['avgNavs'])} strategies")
    print(f"EXCESS_DD_DATA: {len(dd_json)} chars, {len(excess_dd_data['funds'])} funds, {len(excess_dd_data['avgNavs'])} strategies")

    # ── Build HTML ──
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>量化私募业绩看板</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root {{
  --bg-deep: #080c12;
  --bg-card: #11161d;
  --bg-card-hover: #161c25;
  --bg-input: #1a1f2a;
  --border: #1e2733;
  --border-active: #d4a050;
  --text-primary: #e8e4dd;
  --text-secondary: #8b847a;
  --text-muted: #5a5550;
  --accent: #d4a050;
  --accent-glow: rgba(212,160,80,0.12);
  --green: #4ade80;
  --green-bg: rgba(74,222,128,0.10);
  --red: #f87171;
  --red-bg: rgba(248,113,113,0.10);
  --blue: #60a5fa;
  --teal: #2dd4bf;
  --radius: 6px;
  --transition: 0.2s cubic-bezier(0.4,0,0.2,1);
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  font-family:'SF Mono',SFMono-Regular,ui-monospace,'Cascadia Code',Consolas,monospace;
  background:var(--bg-deep);
  background-image:
    radial-gradient(ellipse at 20% 20%, rgba(212,160,80,0.03) 0%, transparent 60%),
    radial-gradient(ellipse at 80% 80%, rgba(96,165,250,0.02) 0%, transparent 60%);
  color:var(--text-primary);
  padding:20px 24px;
  min-height:100vh;
  -webkit-font-smoothing:antialiased;
}}
h2{{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:15px;font-weight:600;margin-bottom:14px;color:var(--text-primary);
  border-left:3px solid var(--accent);padding-left:12px;letter-spacing:0.02em;
}}
.summary{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
.card{{
  background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);
  padding:18px 20px;flex:1;min-width:150px;text-align:center;
  transition:border-color var(--transition),box-shadow var(--transition);
  position:relative;overflow:hidden;
}}
.card::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,var(--accent),transparent);
  opacity:0;transition:opacity var(--transition);
}}
.card:hover{{border-color:var(--border-active);box-shadow:0 0 20px var(--accent-glow)}}
.card:hover::before{{opacity:1}}
.card .val{{
  font-size:26px;font-weight:700;color:var(--accent);
  font-family:'SF Mono',SFMono-Regular,Consolas,monospace;
  letter-spacing:-0.02em;
}}
.card .lbl{{font-size:11px;color:var(--text-secondary);margin-top:5px;text-transform:uppercase;letter-spacing:0.06em;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
.panel{{
  background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);
  padding:18px;margin-bottom:16px;
  transition:border-color var(--transition);
}}
.panel:hover{{border-color:#2a3340}}
.chart{{width:100%;height:420px}}
.toolbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}}
.toolbar label{{
  font-size:12px;color:var(--text-secondary);font-weight:500;
  font-family:-apple-system,BlinkMacSystemFont,sans-serif;
  text-transform:uppercase;letter-spacing:0.04em;
}}
.toolbar select,.toolbar input{{
  padding:5px 10px;border:1px solid var(--border);border-radius:4px;
  font-size:13px;background:var(--bg-input);color:var(--text-primary);
  font-family:'SF Mono',SFMono-Regular,Consolas,monospace;
  transition:border-color var(--transition),box-shadow var(--transition);
  outline:none;
}}
.toolbar select:focus,.toolbar input:focus{{
  border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-glow);
}}
.toolbar input::placeholder{{color:var(--text-muted)}}
.toolbar button{{
  padding:5px 14px;border:1px solid var(--accent);border-radius:4px;
  font-size:13px;background:transparent;color:var(--accent);cursor:pointer;
  font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-weight:500;
  transition:all var(--transition);
}}
.toolbar button:hover{{background:var(--accent);color:#0a0e14}}
.nav-up{{color:var(--red);font-weight:600}}
.nav-down{{color:var(--green);font-weight:600}}
.tag{{padding:2px 8px;border-radius:3px;font-size:11px;font-weight:600;font-family:'SF Mono',SFMono-Regular,Consolas,monospace}}
.tag.up{{background:var(--red-bg);color:var(--red)}}
.tag.down{{background:var(--green-bg);color:var(--green)}}
.rank-table{{
  width:100%;border-collapse:collapse;font-size:12px;
  font-family:'SF Mono',SFMono-Regular,Consolas,monospace;
}}
.rank-table th{{
  background:#181f2a;padding:8px 6px;border:1px solid var(--border);
  position:sticky;top:0;z-index:1;white-space:nowrap;
  color:var(--text-secondary);font-weight:600;font-size:11px;
  text-transform:uppercase;letter-spacing:0.04em;
}}
.rank-table td{{
  padding:5px 6px;border:1px solid #1a202a;text-align:center;white-space:nowrap;
  color:var(--text-primary);transition:background var(--transition);
}}
.rank-table tr:hover td{{background:var(--bg-card-hover)}}
.rank-table tbody tr{{transition:background var(--transition)}}
/* Sticky left columns */
.rank-table th.sl,.rank-table td.sl{{position:sticky}}
.rank-table th.sl{{background:#181f2a}}
.rank-table td.sl{{background:var(--bg-deep)}}
.rank-table tr:hover td.sl{{background:var(--bg-card-hover)}}
body.light .rank-table th.sl{{background:#f0f5ff}}
body.light .rank-table td.sl{{background:#fafbff}}
.tabs{{
  display:flex;gap:4px;margin-bottom:24px;padding:4px;
  background:var(--bg-card);border:1px solid var(--border);border-radius:8px;
  width:fit-content;
}}
.tab-btn{{
  padding:9px 20px;font-size:14px;font-weight:600;cursor:pointer;
  border:none;background:transparent;color:var(--text-secondary);
  border-radius:6px;transition:all var(--transition);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
}}
.tab-btn:hover{{color:var(--text-primary);background:rgba(255,255,255,0.03)}}
.tab-btn.active{{
  color:var(--accent);background:rgba(212,160,80,0.08);
  box-shadow:0 0 12px var(--accent-glow);
}}
body.light{{
  --bg-deep:#f5f6fa;--bg-card:#fff;--bg-card-hover:#f8f9fb;--bg-input:#fff;
  --border:#e0e0e0;--border-active:#1677ff;
  --text-primary:#2c3e50;--text-secondary:#666;--text-muted:#999;
  --accent:#1677ff;--accent-glow:rgba(22,119,255,0.12);
  --green:#27ae60;--green-bg:rgba(39,174,96,0.08);
  --red:#e74c3c;--red-bg:rgba(231,76,60,0.08);
  --blue:#3498db;--teal:#1abc9c;
}}
body.light .card::before{{background:linear-gradient(90deg,transparent,var(--accent),transparent)}}
body.light .tab-btn.active{{color:var(--accent);background:rgba(22,119,255,0.08);box-shadow:0 0 12px var(--accent-glow)}}
body.light .toolbar select:focus,body.light .toolbar input:focus{{box-shadow:0 0 0 2px var(--accent-glow)}}
body.light .toolbar button{{border-color:var(--accent);color:var(--accent)}}
body.light .toolbar button:hover{{background:var(--accent);color:#fff}}
body.light .rank-table th{{background:#f0f5ff}}
#themeToggle{{
  background:var(--bg-card);border:1px solid var(--border);border-radius:20px;
  color:var(--text-secondary);cursor:pointer;font-size:13px;padding:6px 14px;
  font-family:-apple-system,BlinkMacSystemFont,sans-serif;
  transition:all var(--transition);white-space:nowrap;
}}
#themeToggle:hover{{border-color:var(--accent);color:var(--accent)}}
#pwOverlay{{position:fixed;top:0;left:0;width:100%;height:100%;background:var(--bg-deep);z-index:9999;display:flex;align-items:center;justify-content:center;flex-direction:column;transition:opacity 0.4s}}
#pwOverlay.hide{{opacity:0;pointer-events:none}}
.pw-card{{background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:40px 36px;text-align:center;max-width:380px;width:90%}}
.pw-card h2{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:18px;margin-bottom:8px;border:none;padding:0;display:block;color:var(--text-primary)}}
.pw-sub{{color:var(--text-secondary);font-size:12px;margin-bottom:24px;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
.pw-card input{{width:100%;padding:10px 14px;background:var(--bg-input);border:1px solid var(--border);border-radius:var(--radius);color:var(--text-primary);font-size:16px;text-align:center;font-family:'SF Mono',SFMono-Regular,Consolas,monospace;outline:none;letter-spacing:0.3em;transition:border-color var(--transition)}}
.pw-card input:focus{{border-color:var(--accent)}}
.pw-card button{{width:100%;margin-top:14px;padding:10px;background:var(--accent);color:#0a0a0a;border:none;border-radius:var(--radius);font-size:14px;font-weight:600;cursor:pointer;font-family:-apple-system,BlinkMacSystemFont,sans-serif;transition:opacity var(--transition)}}
.pw-card button:hover{{opacity:0.85}}
.pw-err{{color:var(--red);font-size:12px;margin-top:10px;min-height:18px;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
@keyframes shake{{0%,100%{{transform:translateX(0)}}20%,60%{{transform:translateX(-6px)}}40%,80%{{transform:translateX(6px)}}}}
.shake{{animation:shake 0.4s}}
.fund-link{{cursor:pointer;color:var(--accent);text-decoration:none;transition:all var(--transition)}}
.fund-link:hover{{color:#fff;text-decoration:underline}}
.modal-overlay{{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(2,2,8,0.85);z-index:10000;display:none;align-items:center;justify-content:center}}
.modal-overlay.show{{display:flex}}
.modal-content{{background:var(--bg-card);border:1px solid var(--border);border-radius:10px;width:95%;max-width:1300px;max-height:92vh;overflow-y:auto;display:flex;flex-direction:column}}
.modal-header{{display:flex;align-items:center;justify-content:space-between;padding:20px 24px;border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--bg-card);z-index:10;border-radius:10px 10px 0 0}}
.modal-header h2{{font-size:16px;margin:0;border:none;padding:0}}
.modal-close{{background:none;border:1px solid var(--border);color:var(--text-secondary);font-size:18px;cursor:pointer;padding:4px 12px;border-radius:var(--radius);transition:all var(--transition);line-height:1}}
.modal-close:hover{{border-color:var(--accent);color:var(--accent)}}
.modal-body{{padding:20px 24px}}
.modal-metrics{{display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap}}
.modal-mcard{{background:var(--bg-deep);border:1px solid var(--border);border-radius:6px;padding:12px 16px;flex:1;min-width:90px;text-align:center}}
.modal-mcard .mv{{font-size:18px;font-weight:700;color:var(--accent);font-family:'SF Mono',SFMono-Regular,Consolas,monospace}}
.modal-mcard .ml{{font-size:10px;color:var(--text-muted);margin-top:2px;text-transform:uppercase;letter-spacing:0.04em;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
.range-bar{{display:flex;gap:12px;align-items:center;margin-bottom:16px;flex-wrap:wrap;padding:10px 14px;background:var(--bg-deep);border-radius:6px;border:1px solid var(--border)}}
.range-bar label{{font-size:11px;color:var(--text-secondary);font-family:-apple-system,BlinkMacSystemFont,sans-serif;text-transform:uppercase;letter-spacing:0.04em}}
.range-bar select{{padding:5px 8px;background:var(--bg-input);border:1px solid var(--border);border-radius:4px;color:var(--text-primary);font-size:12px;font-family:'SF Mono',SFMono-Regular,Consolas,monospace;outline:none}}
.range-bar select:focus{{border-color:var(--accent)}}
.chart-inline{{display:flex;gap:16px}}
.chart-inline .chart-half{{flex:1;height:350px}}
@media(max-width:900px){{.chart-inline{{flex-direction:column}}.chart-inline .chart-half{{height:300px}}}}
</style></head><body>
<div id="pwOverlay"><div class="pw-card"><h2>🔐 量化私募业绩看板</h2><div class="pw-sub">请输入访问密码</div><input type="password" id="pwInput" placeholder="······" autofocus><button onclick="checkPw()">验 证</button><div class="pw-err" id="pwErr"></div></div></div><div id="app" style="display:none">
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--border)">
<h1 style="font-size:20px;color:var(--text-primary);margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-weight:700;letter-spacing:-0.01em"><span style="color:var(--accent)">■</span> 量化私募业绩看板</h1>
<div style="display:flex;align-items:center;gap:16px">
<span style="color:var(--text-muted);font-size:11px;font-family:'SF Mono',SFMono-Regular,Consolas,monospace">数据来源：点睛业绩放送 · 更新至{abs_data['dates'][-1]}</span>
<button id="themeToggle" onclick="toggleTheme()">☀ 浅色</button>
</div>
</div>
<div class="tabs">
  <button class="tab-btn active" id="tabAbs" onclick="switchTab('abs')">📈 绝对收益</button>
  <button class="tab-btn" id="tabExc" onclick="switchTab('excess')">📊 超额收益</button>
  <button class="tab-btn" id="tabDD" onclick="switchTab('excess_dd')">📉 超额回撤</button>
</div>
<div class="summary">
<div class="card"><div class="val" id="totalFunds">-</div><div class="lbl" id="lblTotalFunds">产品总数</div></div>
<div class="card"><div class="val" id="avgNav">-</div><div class="lbl" id="lblAvgNav">平均累计净值</div></div>
<div class="card"><div class="val" id="bestNav">-</div><div class="lbl" id="lblBestNav">最高累计净值</div></div>
<div class="card"><div class="val" id="upPct">-</div><div class="lbl" id="lblUpPct">正收益占比</div></div>
<div class="card"><div class="val" id="dataWeeks">-</div><div class="lbl">数据周数</div></div>
</div>
<div class="panel"><h2 id="hdr-strategy">① 策略走势 + 基准指数</h2><div class="chart" id="chartStrategy"></div></div>
<div class="panel"><h2 id="hdr-grid">② 策略净值对比</h2><div class="toolbar"><label>策略</label><select id="gridStrategy"><option value="">请选择</option></select><label>规模</label><select id="gridSize"><option value="all">全部规模</option></select><label id="lblGridBench">基准线</label><select id="gridBench" style="width:140px;"><option value="">无基准线</option></select><input type="text" id="gridSearch" placeholder="搜索管理人..." style="width:150px;"><span style="color:#888;font-size:12px" id="gridCount"></span></div><div class="chart" id="chartGrid"></div></div>
<div class="panel" id="panelWR"><h2 id="hdr-wr">③ 周度收益排名</h2><div class="toolbar"><label>周</label><select id="wrWeek"></select><label>策略</label><select id="wrStrategy"><option value="all">全部策略</option></select><label>规模</label><select id="wrSize"><option value="all">全部规模</option></select><input type="text" id="wrSearch" placeholder="搜索管理人..." style="width:150px;"><span style="color:#888;font-size:12px" id="wrCount"></span></div><div style="overflow-x:auto;max-height:600px;overflow-y:auto;"><table class="rank-table" id="tableWR"><thead></thead><tbody></tbody></table></div></div>
<div class="panel"><h2 id="hdr-ytd">④ 今年以来收益排名</h2><div class="toolbar"><label>策略</label><select id="ytdStrategy"><option value="all">全部策略</option></select><label>规模</label><select id="ytdSize"><option value="all">全部规模</option></select><input type="text" id="ytdSearch" placeholder="搜索管理人..." style="width:150px;"><span style="color:#888;font-size:12px" id="ytdCount"></span></div><div style="overflow-x:auto;max-height:600px;overflow-y:auto;"><table class="rank-table" id="tableYTD"><thead></thead><tbody></tbody></table></div></div>
<div class="panel"><h2 id="hdr-fund">⑤ 单基金对比</h2><div class="toolbar"><label>策略</label><select id="filterStrategy"><option value="all">全部策略</option></select><label>基金</label><select id="pickerFund" style="width:300px;"></select><button onclick="window.addLine()" style="padding:4px 12px;">+对比</button><button onclick="window.clearLines()" style="padding:4px 12px;">清除</button><label id="lblFundBench">基准线</label><select id="fundBench" style="width:140px;"><option value="">无基准线</option></select></div><div class="chart" id="chartFund"></div></div>
<div class="panel"><h2 id="hdr-matrix">⑥ 累计净值排名矩阵</h2><div class="toolbar"><label>策略</label><select id="filterRankStrategy"><option value="all">全部策略</option></select><label>规模</label><select id="filterRankSize"><option value="all">全部规模</option></select><input type="text" id="searchRank" placeholder="搜索管理人..." style="width:180px;"></div><div style="overflow-x:auto;max-height:600px;overflow-y:auto;"><table class="rank-table" id="tableRank"><thead></thead><tbody></tbody></table></div></div>
<div class="panel" id="panelRankMatrix"><h2 id="hdr-rankmatrix">⑦ 收益排名矩阵</h2><div class="toolbar"><label>策略</label><select id="rankMatrixStrategy"><option value="all">全部策略</option></select><label>规模</label><select id="rankMatrixSize"><option value="all">全部规模</option></select><input type="text" id="rankMatrixSearch" placeholder="搜索管理人..." style="width:150px;"><span style="color:#888;font-size:12px" id="rankMatrixCount"></span></div><div style="overflow-x:auto;max-height:600px;overflow-y:auto;"><table class="rank-table" id="tableRankMatrix"><thead></thead><tbody></tbody></table></div></div>
<div class="panel" id="panelExcessMatrix" style="display:none;"><h2>⑧ 周超额分析矩阵</h2><div class="toolbar"><label>策略</label><select id="excessMatrixStrategy"><option value="all">全部策略</option></select><label>规模</label><select id="excessMatrixSize"><option value="all">全部规模</option></select><input type="text" id="excessMatrixSearch" placeholder="搜索管理人..." style="width:150px;"><span style="color:#888;font-size:12px" id="excessMatrixCount"></span></div><div style="overflow-x:auto;max-height:600px;overflow-y:auto;"><table class="rank-table" id="tableExcessMatrix"><thead></thead><tbody></tbody></table></div></div>
<script>
var ABS_DATA = {abs_json};
var EXCESS_DATA = {exc_json};
var EXCESS_DD_DATA = {dd_json};
var DATA = ABS_DATA;
var IS_EXCESS = false;
var IS_EXCESS_DD = false;
var currentTheme = (localStorage.getItem('dashboardTheme')||'dark');
var currentTab = 'abs';
var TS = {{
  dark: {{tbg:'#1a1f2a',tbc:'#2a3340',ttc:'#e8e4dd',alc:'#8b847a',slc:'#1e2733'}},
  light:{{tbg:'#fff',tbc:'#e8e8e8',ttc:'#2c3e50',alc:'#999',slc:'#eee'}}
}};
function applyTheme() {{
  document.body.className = currentTheme === 'light' ? 'light' : '';
  document.getElementById('themeToggle').innerHTML = currentTheme === 'light' ? '☾ 深色' : '☀ 浅色';
  localStorage.setItem('dashboardTheme', currentTheme);
}}
function toggleTheme() {{
  currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme();
  switchTab(currentTab);
}}
applyTheme();

var COLORS = ["#f87171","#60a5fa","#4ade80","#fbbf24","#c084fc","#2dd4bf","#fb923c","#94a3b8","#f472b6","#38bdf8","#f97316","#a78bfa"];
var BENCH_COLORS = {{"沪深300":"#f87171","中证500":"#fbbf24","中证800":"#c084fc","中证1000":"#60a5fa","中证2000":"#2dd4bf","A500":"#fb923c"}};
var SIZE_ORDER = ['100亿以上','50~100亿','20~50亿','10~20亿','5~10亿','0~5亿'];

var cS = null, cG = null, cF = null, extraLines = [];
// Single resize handler — registered ONCE. It references the global chart
// vars, which switchTab/initAll reassign; no listener is added per tab switch.
window.addEventListener('resize',function(){{if(cS)cS.resize();if(cG)cG.resize();if(cF)cF.resize();if(productChart1)productChart1.resize();if(productChart2)productChart2.resize();}});

function makeBenchSeries(bname, showSymbol) {{
  if (!DATA.benchData) return null;
  var bd = DATA.benchData[bname]; if (!bd) return null;
  var benchLookup = {{}}; bd.dates.forEach(function(d,i){{ benchLookup[d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6,8)] = bd.navs[i]; }});
  var data = []; DATA.dates.forEach(function(d){{ if (benchLookup[d] !== undefined) {{ data.push([d.slice(5), benchLookup[d]]); }} }});
  return {{ name: bname, type:'line', data:data, smooth:true, symbol: showSymbol ? 'diamond' : 'none', symbolSize: showSymbol ? 6 : 0, lineStyle:{{width:3, color:BENCH_COLORS[bname]||'#000', type:'dashed'}}, itemStyle:{{color:BENCH_COLORS[bname]||'#000'}}, z:10 }};
}}

function switchTab(tab) {{
  if (cS) cS.dispose(); if (cG) cG.dispose(); if (cF) cF.dispose();
  cS = null; cG = null; cF = null; extraLines = [];
  closeProductModal();

  currentTab = tab;
  IS_EXCESS = (tab === 'excess' || tab === 'excess_dd');
  IS_EXCESS_DD = (tab === 'excess_dd');
  if (tab === 'excess_dd') DATA = EXCESS_DD_DATA;
  else if (tab === 'excess') DATA = EXCESS_DATA;
  else DATA = ABS_DATA;

  document.getElementById('tabAbs').className = (tab === 'abs') ? 'tab-btn active' : 'tab-btn';
  document.getElementById('tabExc').className = (tab === 'excess') ? 'tab-btn active' : 'tab-btn';
  document.getElementById('tabDD').className = (tab === 'excess_dd') ? 'tab-btn active' : 'tab-btn';

  // Show/hide benchmark UI (only abs tab shows benchmarks)
  var benchDisplay = (tab !== 'abs') ? 'none' : '';
  // Weekly ranking hidden in drawdown tab only
  document.getElementById('panelWR').style.display = (tab === 'excess_dd') ? 'none' : '';
  document.getElementById('panelExcessMatrix').style.display = (tab === 'excess') ? '' : 'none';
  document.getElementById('lblGridBench').style.display = benchDisplay;
  document.getElementById('gridBench').style.display = benchDisplay;
  document.getElementById('lblFundBench').style.display = benchDisplay;
  document.getElementById('fundBench').style.display = benchDisplay;

  initAll();
}}

function initAll() {{
  // Reset dropdowns with default options
  ['filterStrategy','filterRankStrategy','wrStrategy','ytdStrategy','rankMatrixStrategy','excessMatrixStrategy'].forEach(function(id) {{
    document.getElementById(id).innerHTML = '<option value="all">全部策略</option>';
  }});
  ['filterRankSize','gridSize','rankMatrixSize','excessMatrixSize','wrSize','ytdSize'].forEach(function(id) {{
    document.getElementById(id).innerHTML = '<option value="all">全部规模</option>';
  }});
  document.getElementById('gridStrategy').innerHTML = '<option value="">请选择</option>';
  ['gridBench','fundBench'].forEach(function(id) {{
    var sel = document.getElementById(id); sel.innerHTML = '<option value="">无基准线</option>';
  }});

  var dates = DATA.dates.map(function(d){{return d.slice(5);}});
  var strats = Object.keys(DATA.avgNavs);
  var benchNames = DATA.benchData ? Object.keys(DATA.benchData) : [];

  // Update section headers for abs vs excess mode
  document.getElementById('hdr-strategy').textContent = IS_EXCESS_DD ? '① 超额回撤走势' : (IS_EXCESS ? '① 策略超额走势' : '① 策略走势 + 基准指数');
  document.getElementById('hdr-grid').textContent = IS_EXCESS_DD ? '② 产品超额回撤对比' : (IS_EXCESS ? '② 产品超额净值对比' : '② 策略净值对比');
  document.getElementById('hdr-wr').textContent = IS_EXCESS ? '③ 周度超额收益排名' : '③ 周度收益排名';
  document.getElementById('hdr-ytd').textContent = IS_EXCESS_DD ? '③ 今年以来最大超额回撤排名' : (IS_EXCESS ? '④ 今年以来超额排名' : '④ 今年以来收益排名');
  document.getElementById('hdr-fund').textContent = IS_EXCESS_DD ? '④ 单基金对比' : (IS_EXCESS ? '⑤ 单基金对比' : '⑤ 单基金对比');
  document.getElementById('hdr-matrix').textContent = IS_EXCESS_DD ? '⑤ 超额回撤矩阵' : (IS_EXCESS ? '⑥ 超额净值排名矩阵' : '⑥ 累计净值排名矩阵');
  document.getElementById('hdr-rankmatrix').textContent = IS_EXCESS_DD ? '⑥ 超额回撤排名' : (IS_EXCESS ? '⑦ 超额收益排名矩阵' : '⑦ 收益排名矩阵');

  // Update summary card labels for drawdown mode
  document.getElementById('lblAvgNav').textContent = IS_EXCESS_DD ? '平均超额回撤' : (IS_EXCESS ? '平均超额净值' : '平均累计净值');
  document.getElementById('lblBestNav').textContent = IS_EXCESS_DD ? '最小超额回撤' : (IS_EXCESS ? '最高超额净值' : '最高累计净值');
  document.getElementById('lblUpPct').textContent = IS_EXCESS_DD ? '峰值占比' : (IS_EXCESS ? '正超额占比' : '正收益占比');

  // Strategy dropdowns
  ['filterStrategy','filterRankStrategy','gridStrategy','wrStrategy','ytdStrategy','rankMatrixStrategy','excessMatrixStrategy'].forEach(function(id) {{
    var sel = document.getElementById(id);
    strats.forEach(function(s){{sel.innerHTML+='<option value="'+s+'">'+s+'</option>';}});
  }});

  // Benchmark dropdowns (only in abs mode)
  if (!IS_EXCESS) {{
    ['gridBench','fundBench'].forEach(function(sid) {{
      var sel = document.getElementById(sid);
      benchNames.forEach(function(b){{ sel.innerHTML += '<option value="'+b+'">'+b+'</option>'; }});
    }});
  }}

  // Summary cards
  var finals = []; DATA.funds.forEach(function(f){{var arr=IS_EXCESS_DD?f.excesses:f.navs,v=arr.filter(function(n){{return n!==null;}});if(v.length)finals.push(v[v.length-1]);}});
  document.getElementById('totalFunds').textContent = DATA.funds.length;
  if(IS_EXCESS_DD){{
    document.getElementById('avgNav').textContent = (finals.reduce(function(a,b){{return a+b;}},0)/finals.length*100).toFixed(2)+'%';
    document.getElementById('bestNav').textContent = (Math.max.apply(null,finals)*100).toFixed(2)+'%';
    document.getElementById('upPct').textContent = (finals.filter(function(v){{return v===0;}}).length/finals.length*100).toFixed(0)+'%';
  }}else{{
    document.getElementById('avgNav').textContent = (finals.reduce(function(a,b){{return a+b;}},0)/finals.length).toFixed(4);
    document.getElementById('bestNav').textContent = Math.max.apply(null,finals).toFixed(4);
    document.getElementById('upPct').textContent = (finals.filter(function(v){{return v>1;}}).length/finals.length*100).toFixed(0)+'%';
  }}
  document.getElementById('dataWeeks').textContent = DATA.dates.length;

  // 1. Strategy chart
  cS = echarts.init(document.getElementById('chartStrategy'));
  var sSeries=[], ci=0;
  Object.keys(DATA.avgNavs).forEach(function(s) {{
    var d=[]; DATA.avgNavs[s].forEach(function(n,j){{if(n!==null)d.push([dates[j], IS_EXCESS ? n-1.0 : n]);}});
    sSeries.push({{name:s,type:'line',data:d,smooth:true,symbol:'circle',symbolSize:3,lineStyle:{{width:2,color:COLORS[ci%COLORS.length]}},itemStyle:{{color:COLORS[ci%COLORS.length]}}}});
    ci++;
  }});
  benchNames.forEach(function(b){{ var bs = makeBenchSeries(b); if(bs) sSeries.push(bs); }});
  var sYaf=IS_EXCESS?function(v){{return (v*100).toFixed(1)+'%';}}:function(v){{return v.toFixed(3);}};
  cS.setOption({{backgroundColor:'transparent',tooltip:{{trigger:'axis',valueFormatter:IS_EXCESS?function(v){{return v!=null?(v*100).toFixed(2)+'%':'-';}}:undefined,backgroundColor:TS[currentTheme].tbg,borderColor:TS[currentTheme].tbc,textStyle:{{color:TS[currentTheme].ttc}}}},legend:{{bottom:0,type:'scroll',textStyle:{{color:TS[currentTheme].alc}},pageTextStyle:{{color:TS[currentTheme].alc}}}},grid:{{left:IS_EXCESS?60:50,right:30,top:20,bottom:40}},xAxis:{{type:'category',data:dates,axisLabel:{{rotate:45,fontSize:10,color:TS[currentTheme].alc}},axisLine:{{lineStyle:{{color:TS[currentTheme].slc}}}},boundaryGap:false}},yAxis:{{type:'value',min:IS_EXCESS?undefined:0.82,scale:IS_EXCESS,axisLabel:{{formatter:sYaf,color:TS[currentTheme].alc}},splitLine:{{lineStyle:{{color:TS[currentTheme].slc}}}},axisLine:{{lineStyle:{{color:TS[currentTheme].slc}}}}}},series:sSeries}});
  // resize: single global listener (registered once at top)

  // 2. Grid chart
  cG = echarts.init(document.getElementById('chartGrid'));
  // Rebuild a size dropdown for a strategy choice, preserving the user's
  // current size when it stays valid under the new strategy — so you can pick
  // size first then strategy without the size selection being wiped.
  function syncSizeDropdown(sel, strategyValue, allMarker) {{
    var prevSize = sel.value;
    var sizes = (strategyValue !== allMarker && DATA.strategySizes[strategyValue]) ? DATA.strategySizes[strategyValue] : SIZE_ORDER;
    var opts = '<option value="all">全部规模</option>';
    sizes.forEach(function(sz){{ opts += '<option value="'+sz+'">'+sz+'</option>'; }});
    sel.innerHTML = opts;
    sel.value = (prevSize !== 'all' && sizes.indexOf(prevSize) >= 0) ? prevSize : 'all';
  }}
  function updateGridSizes() {{
    var strat=document.getElementById('gridStrategy').value, sel=document.getElementById('gridSize');
    sel.innerHTML='<option value="all">全部规模</option>';
    if(strat&&DATA.strategySizes[strat]){{DATA.strategySizes[strat].forEach(function(sz){{sel.innerHTML+='<option value="'+sz+'">'+sz+'</option>';}});}}
    drawGridChart();
  }}
  function drawGridChart() {{
    var strat=document.getElementById('gridStrategy').value, size=document.getElementById('gridSize').value, bench=document.getElementById('gridBench').value, search=document.getElementById('gridSearch').value.toLowerCase(), countEl=document.getElementById('gridCount');
    if(!strat){{cG.setOption({{title:{{text:'请选择策略',left:'center',top:'center'}}}},true);countEl.textContent='';return;}}
    var matched=DATA.funds.filter(function(f){{return f.strategy===strat&&(size==='all'||f.size===size)&&(!search||f.company.toLowerCase().indexOf(search)>=0);}});
    if(IS_EXCESS){{matched.sort(function(a,b){{var va=a.excesses.filter(function(n){{return n!==null;}}),vb=b.excesses.filter(function(n){{return n!==null;}});return (vb[vb.length-1]||-999)-(va[va.length-1]||-999);}});}}
    else{{matched.sort(function(a,b){{var va=a.navs.filter(function(n){{return n!==null;}}),vb=b.navs.filter(function(n){{return n!==null;}});return (vb[vb.length-1]||0)-(va[va.length-1]||0);}});}}
    countEl.textContent=matched.length+' 只'; var display=matched.slice(0,30), series=[];
    display.forEach(function(f,i){{var arr=IS_EXCESS?f.excesses:f.navs, d=[];arr.forEach(function(n,j){{if(n!==null)d.push([dates[j],n]);}});series.push({{name:f.company+' ['+f.size+']',type:'line',data:d,smooth:true,symbol:'circle',symbolSize:3,lineStyle:{{width:1.5,color:COLORS[i%COLORS.length]}},itemStyle:{{color:COLORS[i%COLORS.length]}},emphasis:{{focus:'series',lineStyle:{{width:3}},symbolSize:6}}}});}});
    if(bench&&!IS_EXCESS){{ var bs = makeBenchSeries(bench, true); if(bs) series.push(bs); }}
    var ttf=IS_EXCESS_DD?function(p){{return '<b>'+p.seriesName+'</b><br/>'+p.value[0]+'<br/>超额回撤: <b>'+(p.value[1]*100).toFixed(2)+'%</b>';}}:(IS_EXCESS?function(p){{return '<b>'+p.seriesName+'</b><br/>'+p.value[0]+'<br/>超额收益: <b>'+(p.value[1]*100).toFixed(2)+'%</b>';}}:function(p){{return '<b>'+p.seriesName+'</b><br/>'+p.value[0]+'<br/>净值: <b>'+p.value[1].toFixed(4)+'</b>';}});
    var yaf=IS_EXCESS?function(v){{return (v*100).toFixed(1)+'%';}}:function(v){{return v.toFixed(3);}};
    cG.setOption({{backgroundColor:'transparent',tooltip:{{trigger:'item',formatter:ttf,backgroundColor:TS[currentTheme].tbg,borderColor:TS[currentTheme].tbc,textStyle:{{color:TS[currentTheme].ttc}}}},legend:{{show:false}},grid:{{left:60,right:30,top:20,bottom:30}},xAxis:{{type:'category',data:dates,axisLabel:{{rotate:45,fontSize:10,color:TS[currentTheme].alc}},axisLine:{{lineStyle:{{color:TS[currentTheme].slc}}}},boundaryGap:false}},yAxis:{{type:'value',scale:true,axisLabel:{{formatter:yaf,color:TS[currentTheme].alc}},splitLine:{{lineStyle:{{color:TS[currentTheme].slc}}}},axisLine:{{lineStyle:{{color:TS[currentTheme].slc}}}}}},series:series}},true);
  }}
  // resize: single global listener (registered once at top)

  // 3. Weekly ranking
  var wrWeekSel=document.getElementById('wrWeek');
  wrWeekSel.innerHTML = '';
  DATA.weekLabels.forEach(function(wl){{var info=DATA.weekInfo[wl]||wl;wrWeekSel.innerHTML+='<option value="'+wl+'">'+wl+' ('+info+')</option>';}});
  wrWeekSel.value=DATA.weekLabels[DATA.weekLabels.length-1];
  function updateWRTable() {{
    var week=document.getElementById('wrWeek').value, strat=document.getElementById('wrStrategy').value, size=document.getElementById('wrSize').value, search=document.getElementById('wrSearch').value.toLowerCase(), countEl=document.getElementById('wrCount');
    var data=DATA.weeklyData[week]||[], filtered=data.filter(function(r){{if(strat!=='all'&&r.strategy!==strat)return false;if(size!=='all'&&r.size!==size)return false;if(search&&r.company.toLowerCase().indexOf(search)<0)return false;return true;}});
    var n=filtered.length;filtered.sort(function(a,b){{return b.weekly_return-a.weekly_return;}}); filtered.forEach(function(r,i){{r.pct=n>1?Math.round((n-i)/n*100):100;}}); countEl.textContent=n+' 条';
    var maxAbs=0;filtered.forEach(function(r){{maxAbs=Math.max(maxAbs,Math.abs(r.weekly_return));}});
    if (IS_EXCESS) {{
      document.querySelector('#tableWR thead').innerHTML='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>周超额</th><th>收益柱</th><th>分位</th></tr>';
    }} else {{
      document.querySelector('#tableWR thead').innerHTML='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>周收益</th><th>周超额</th><th>收益柱</th><th>分位</th></tr>';
    }}
    var tbody='';filtered.forEach(function(r,i){{var retPct=(r.weekly_return*100).toFixed(2),isUp=r.weekly_return>=0,cls=isUp?'nav-up':'nav-down',barW=maxAbs>0?Math.abs(r.weekly_return)/maxAbs*100:100,barColor=isUp?'#e74c3c':'#27ae60';
      if(IS_EXCESS){{
        tbody+='<tr><td><b>'+(i+1)+'</b></td><td>'+fundLink(r.company,r.strategy)+'</td><td>'+r.strategy+'</td><td>'+r.size+'</td><td class="'+cls+'">'+(isUp?'+':'')+retPct+'%</td><td style="width:180px;"><span style="display:inline-block;width:'+barW+'%;height:12px;background:'+barColor+';border-radius:3px;vertical-align:middle;"></span></td><td>'+r.pct+'%</td></tr>';
      }}else{{
        var exPct=r.weekly_excess!==null?(r.weekly_excess*100).toFixed(2):'-';
        tbody+='<tr><td><b>'+(i+1)+'</b></td><td>'+fundLink(r.company,r.strategy)+'</td><td>'+r.strategy+'</td><td>'+r.size+'</td><td class="'+cls+'">'+(isUp?'+':'')+retPct+'%</td><td class="'+(r.weekly_excess!==null&&r.weekly_excess>=0?'nav-up':'nav-down')+'">'+(r.weekly_excess!==null?(r.weekly_excess>=0?'+':'')+exPct+'%':'-')+'</td><td style="width:180px;"><span style="display:inline-block;width:'+barW+'%;height:12px;background:'+barColor+';border-radius:3px;vertical-align:middle;"></span></td><td>'+r.pct+'%</td></tr>';
      }}
    }});
    document.querySelector('#tableWR tbody').innerHTML=tbody;
  }}

  // 4. YTD ranking
  function updateYTDTable() {{
    var strat=document.getElementById('ytdStrategy').value, size=document.getElementById('ytdSize').value, search=document.getElementById('ytdSearch').value.toLowerCase(), countEl=document.getElementById('ytdCount');
    var filtered=DATA.funds.filter(function(f){{if(strat!=='all'&&f.strategy!==strat)return false;if(size!=='all'&&f.size!==size)return false;if(search&&f.company.toLowerCase().indexOf(search)<0)return false;return true;}});
    if(IS_EXCESS_DD){{
      // Drawdown mode: rank by worst (most negative) excess drawdown
      var rows=filtered.map(function(f){{var v=f.excesses.filter(function(n){{return n!==null;}});var worst=v.length?Math.min.apply(null,v):null,cur=v.length?v[v.length-1]:null;return{{company:f.company,strategy:f.strategy,size:f.size,worst:worst,current:cur,weeks:v.length}};}}).filter(function(r){{return r.worst!==null;}}).sort(function(a,b){{return b.worst-a.worst;}});
      var n=rows.length;rows.forEach(function(r,i){{r.pct=n>1?Math.round((n-i)/n*100):100;}}); countEl.textContent=n+' 条';
      var maxAbs=0;rows.forEach(function(r){{maxAbs=Math.max(maxAbs,Math.abs(r.worst));}});
      document.querySelector('#tableYTD thead').innerHTML='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>最大超额回撤</th><th>当前回撤</th><th>回撤柱</th><th>分位</th><th>覆盖</th></tr>';
      var tbody='';rows.forEach(function(r,i){{var worstPct=(r.worst*100).toFixed(2),curPct=r.current!==null?(r.current*100).toFixed(2):'-',barW=maxAbs>0?Math.abs(r.worst)/maxAbs*100:100;tbody+='<tr><td><b>'+(i+1)+'</b></td><td>'+fundLink(r.company,r.strategy)+'</td><td>'+r.strategy+'</td><td>'+r.size+'</td><td class="nav-down">'+worstPct+'%</td><td class="'+(r.current===0?'nav-up':'nav-down')+'">'+curPct+'%</td><td style="width:120px;"><span style="display:inline-block;width:'+barW+'%;height:12px;background:#e74c3c;border-radius:3px;vertical-align:middle;"></span></td><td>'+r.pct+'%</td><td>'+r.weeks+'/'+DATA.dates.length+'</td></tr>';}});
      document.querySelector('#tableYTD tbody').innerHTML=tbody;
    }}else{{
      var rows=filtered.map(function(f){{var v=f.navs.filter(function(n){{return n!==null;}});var latest=v.length?v[v.length-1]:null;return{{company:f.company,strategy:f.strategy,size:f.size,nav:latest,ytd:latest!==null?latest-1:null,first:v.length?v[0]:null,weeks:v.length}};}}).filter(function(r){{return r.nav!==null;}}).sort(function(a,b){{return b.nav-a.nav;}});
      var n=rows.length;rows.forEach(function(r,i){{r.pct=n>1?Math.round((n-i)/n*100):100;}}); countEl.textContent=n+' 条';
      var maxAbs=0;rows.forEach(function(r){{maxAbs=Math.max(maxAbs,Math.abs(r.ytd));}});
      if (IS_EXCESS) {{
        document.querySelector('#tableYTD thead').innerHTML='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>超额净值</th><th>YTD超额</th><th>收益柱</th><th>分位</th><th>覆盖</th></tr>';
      }} else {{
        document.querySelector('#tableYTD thead').innerHTML='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>累计净值</th><th>YTD收益</th><th>收益柱</th><th>分位</th><th>覆盖</th></tr>';
      }}
      var tbody='';rows.forEach(function(r,i){{var ytdPct=(r.ytd*100).toFixed(2),isUp=r.ytd>=0,cls=isUp?'nav-up':'nav-down',barW=maxAbs>0?Math.abs(r.ytd)/maxAbs*100:100,barColor=isUp?'#e74c3c':'#27ae60';tbody+='<tr><td><b>'+(i+1)+'</b></td><td>'+fundLink(r.company,r.strategy)+'</td><td>'+r.strategy+'</td><td>'+r.size+'</td><td class="'+cls+'">'+r.nav.toFixed(4)+'</td><td class="'+cls+'">'+(isUp?'+':'')+ytdPct+'%</td><td style="width:120px;"><span style="display:inline-block;width:'+barW+'%;height:12px;background:'+barColor+';border-radius:3px;vertical-align:middle;"></span></td><td>'+r.pct+'%</td><td>'+r.weeks+'/'+DATA.dates.length+'</td></tr>';}});
      document.querySelector('#tableYTD tbody').innerHTML=tbody;
    }}
  }}

  // 5. Single fund
  cF = echarts.init(document.getElementById('chartFund'));
  extraLines = [];
  function updateFundPicker() {{
    var strat=document.getElementById('filterStrategy').value, sel=document.getElementById('pickerFund');
    sel.innerHTML='';
    DATA.funds.filter(function(f){{return strat==='all'||f.strategy===strat;}}).forEach(function(f){{var v=f.navs.filter(function(n){{return n!==null;}});var latest=v.length?v[v.length-1]:null;var name=f.company+'('+f.strategy+')';sel.innerHTML+='<option value="'+f.company+'|'+f.strategy+'">'+name+' ('+f.size+') '+(latest?latest.toFixed(4):'N/A')+'</option>';}});
    drawFundChart();
  }}
  function addLine(){{var val=document.getElementById('pickerFund').value;if(!val)return;if(extraLines.indexOf(val)<0)extraLines.push(val);drawFundChart();}}
  function clearLines(){{extraLines=[];drawFundChart();}}
  function drawFundChart() {{
    var pv=document.getElementById('pickerFund').value, allVals=[pv].concat(extraLines).filter(Boolean), bench=document.getElementById('fundBench').value, series=[];
    allVals.forEach(function(val,i){{var parts=val.split('|'),name=parts[0],strat=parts.slice(1).join('|');var f=DATA.funds.find(function(f){{return f.company===name&&f.strategy===strat;}});if(!f)return;var arr=IS_EXCESS?f.excesses:f.navs,d=[];arr.forEach(function(n,j){{if(n!==null)d.push([dates[j],n]);}});series.push({{name:name+'('+strat+')',type:'line',data:d,smooth:true,symbol:'circle',symbolSize:5,lineStyle:{{width:3,color:COLORS[i%COLORS.length]}},itemStyle:{{color:COLORS[i%COLORS.length]}}}});}});
    if(bench&&!IS_EXCESS){{var bs=makeBenchSeries(bench);if(bs)series.push(bs);}}
    var fYaf2=IS_EXCESS?function(v){{return (v*100).toFixed(1)+'%';}}:function(v){{return v.toFixed(3);}};
    cF.setOption({{backgroundColor:'transparent',tooltip:{{trigger:'axis',valueFormatter:IS_EXCESS?function(v){{return v!=null?(v*100).toFixed(2)+'%':'-';}}:undefined,backgroundColor:TS[currentTheme].tbg,borderColor:TS[currentTheme].tbc,textStyle:{{color:TS[currentTheme].ttc}}}},legend:{{bottom:0,type:'scroll',textStyle:{{color:TS[currentTheme].alc}},pageTextStyle:{{color:TS[currentTheme].alc}}}},grid:{{left:IS_EXCESS?60:50,right:30,top:20,bottom:40}},xAxis:{{type:'category',data:dates,axisLabel:{{rotate:45,fontSize:10,color:TS[currentTheme].alc}},axisLine:{{lineStyle:{{color:TS[currentTheme].slc}}}},boundaryGap:false}},yAxis:{{type:'value',scale:true,axisLabel:{{formatter:fYaf2,color:TS[currentTheme].alc}},splitLine:{{lineStyle:{{color:TS[currentTheme].slc}}}},axisLine:{{lineStyle:{{color:TS[currentTheme].slc}}}}}},series:series}},true);
  }}
  // resize: single global listener (registered once at top)

  // 6. Ranking matrix
  function updateRankTable() {{
    var strat=document.getElementById('filterRankStrategy').value, size=document.getElementById('filterRankSize').value, search=document.getElementById('searchRank').value.toLowerCase();
    var funds=DATA.funds.filter(function(f){{return strat==='all'||f.strategy===strat;}}).filter(function(f){{return size==='all'||f.size===size;}}).filter(function(f){{return !search||f.company.toLowerCase().indexOf(search)>=0;}}).map(function(f){{var arr=IS_EXCESS?f.excesses:f.navs,v=arr.filter(function(n){{return n!==null;}});var latest=v.length?v[v.length-1]:null;var prev=v.length>=2?v[v.length-2]:null;var worst=IS_EXCESS_DD&&v.length?Math.min.apply(null,v):null;return{{company:f.company,strategy:f.strategy,vals:arr,size:f.size,final:IS_EXCESS_DD?worst:latest,prev:prev,weeks:v.length}};}}).filter(function(f){{return f.final!==null;}}).sort(function(a,b){{return b.final-a.final;}});
    var dates_local = DATA.dates.map(function(d){{return d.slice(5);}});
    var thead='<tr><th class=\"sl\">排名</th><th class=\"sl\">管理人</th><th class=\"sl\">规模</th><th class=\"sl\">策略</th><th>'+(IS_EXCESS_DD?'最大超额回撤':(IS_EXCESS?'最新超额':'最新净值'))+'</th><th>变动</th><th>覆盖</th>';
    dates_local.forEach(function(d){{thead+='<th>'+d+'</th>';}});thead+='</tr>';
    document.querySelector('#tableRank thead').innerHTML=thead;
    var tbody='';funds.forEach(function(f,i){{var ch=f.final!==null&&f.prev!==null?f.final-f.prev:null,chHtml='-';if(ch!==null){{if(IS_EXCESS_DD){{var cls2=ch>0?'down':'up';chHtml='<span class=\"tag '+cls2+'\">'+(ch>=0?'+':'')+(ch*100).toFixed(1)+'%</span>';}}else{{var cls=ch>0?'up':'down';chHtml='<span class=\"tag '+cls+'\">'+(ch>=0?'+':'')+(ch*100).toFixed(1)+'%</span>';}}}}if(IS_EXCESS_DD){{tbody+='<tr><td class=\"sl\"><b>'+(i+1)+'</b></td><td class=\"sl\">'+fundLink(f.company,f.strategy)+'</td><td class="sl">'+f.size+'</td><td class="sl">'+f.strategy+'</td><td class=\"'+(f.final===0?'nav-up':'nav-down')+'\">'+(f.final*100).toFixed(2)+'%</td><td>'+chHtml+'</td><td>'+f.weeks+'/'+DATA.dates.length+'</td>';dates_local.forEach(function(d,j){{var n=f.vals[j];tbody+=n!==null?'<td style=\"color:'+(n===0?'#27ae60':(n>-0.03?'#f39c12':'#e74c3c'))+'\">'+(n*100).toFixed(2)+'%</td>':'<td style=\"color:#ccc\">·</td>';}});}}else if(IS_EXCESS){{tbody+='<tr><td class=\"sl\"><b>'+(i+1)+'</b></td><td class=\"sl\">'+fundLink(f.company,f.strategy)+'</td><td class="sl">'+f.size+'</td><td class="sl">'+f.strategy+'</td><td class=\"'+(f.final>0?'nav-up':'nav-down')+'\">'+(f.final*100).toFixed(2)+'%</td><td>'+chHtml+'</td><td>'+f.weeks+'/'+DATA.dates.length+'</td>';dates_local.forEach(function(d,j){{var n=f.vals[j];tbody+=n!==null?'<td style=\"color:'+(n>0?'#e74c3c':'#27ae60')+'\">'+(n*100).toFixed(2)+'%</td>':'<td style=\"color:#ccc\">·</td>';}});}}else{{tbody+='<tr><td class=\"sl\"><b>'+(i+1)+'</b></td><td class=\"sl\">'+fundLink(f.company,f.strategy)+'</td><td class="sl">'+f.size+'</td><td class="sl">'+f.strategy+'</td><td class=\"'+(f.final>=1?'nav-up':'nav-down')+'\">'+f.final.toFixed(4)+'</td><td>'+chHtml+'</td><td>'+f.weeks+'/'+DATA.dates.length+'</td>';dates_local.forEach(function(d,j){{var n=f.vals[j];tbody+=n!==null?'<td style=\"color:'+(n>=1?'#e74c3c':'#27ae60')+'\">'+n.toFixed(4)+'</td>':'<td style=\"color:#ccc\">·</td>';}});}}tbody+='</tr>';}});
    document.querySelector('#tableRank tbody').innerHTML=tbody;
    fixStickyLeft('tableRank', 7);
  }}

  // 7. Excess rank matrix (excess tab only)
  function updateRankMatrix() {{
    var strat=document.getElementById('rankMatrixStrategy').value, size=document.getElementById('rankMatrixSize').value, search=document.getElementById('rankMatrixSearch').value.toLowerCase();
    var matched=DATA.funds.filter(function(f){{return (strat==='all'||f.strategy===strat)&&(size==='all'||f.size===size)&&(!search||f.company.toLowerCase().indexOf(search)>=0);}});
    matched.sort(function(a,b){{var ra=a.ranks.filter(function(r){{return r!==null;}}),rb=b.ranks.filter(function(r){{return r!==null;}});return(ra.length?ra[ra.length-1]:999)-(rb.length?rb[rb.length-1]:999);}});
    document.getElementById('rankMatrixCount').textContent=matched.length+' 只';
    var dates_local=DATA.dates.map(function(d){{return d.slice(5);}});
    var thead='<tr><th class=\"sl\">排名</th><th class=\"sl\">管理人</th><th class=\"sl\">规模</th><th class=\"sl\">策略</th><th>最新名次</th><th>趋势</th>';
    dates_local.forEach(function(d){{thead+='<th>'+d+'</th>';}});thead+='</tr>';
    document.querySelector('#tableRankMatrix thead').innerHTML=thead;
    var tbody='';matched.forEach(function(f,i){{
      var valid=f.ranks.filter(function(r){{return r!==null;}}),latest=valid.length?valid[valid.length-1]:null,prevRank=valid.length>=2?valid[valid.length-2]:null,ch=latest!==null&&prevRank!==null?prevRank-latest:null,chHtml='-';
      if(ch!==null){{if(ch>0)chHtml='<span class="tag up">↑'+ch+'</span>';else if(ch<0)chHtml='<span class="tag down">↓'+Math.abs(ch)+'</span>';else chHtml='<span style="color:#888">─</span>';}}
      tbody+='<tr><td class="sl"><b>'+(i+1)+'</b></td><td class="sl">'+fundLink(f.company,f.strategy)+'</td><td class="sl">'+f.size+'</td><td class="sl">'+f.strategy+'</td><td><b>'+(latest||'-')+'</b></td><td>'+chHtml+'</td>';
      dates_local.forEach(function(d,j){{var r=f.ranks[j];if(r!==null){{var alpha=Math.max(0.3,1-r/Math.max(valid.length,50)),bg=r<=5?'#27ae60':(r<=10?'#2ecc71':(r<=20?'#f39c12':'#e74c3c'));tbody+='<td style="background:'+bg+';color:#fff;font-weight:600;opacity:'+alpha.toFixed(2)+'">'+r+'</td>';}}else{{tbody+='<td style="color:#ccc">·</td>';}}}});
      tbody+='</tr>';
    }});
    document.querySelector('#tableRankMatrix tbody').innerHTML=tbody;
    fixStickyLeft('tableRankMatrix', 6);
  }}

  // 8. Weekly excess matrix (excess tab only): per-fund single-week excess
  function exWinRate(f) {{
    if (!f.weeklyExcess) return null;
    var vals = f.weeklyExcess.filter(function(v){{return v!==null;}});
    if (!vals.length) return null;
    var up = vals.filter(function(v){{return v>0;}}).length;
    return {{rate: up/vals.length, up: up, total: vals.length, avg: vals.reduce(function(a,b){{return a+b;}},0)/vals.length}};
  }}
  function exCellStyle(v) {{
    if (v===null || v===undefined) return 'color:#888;';
    var abs = Math.min(Math.abs(v), 0.035)/0.035;
    var a = 0.16 + abs*0.74;
    var rgb = v>=0 ? '231,76,60' : '39,174,96';
    var txt = a>0.5 ? '#fff' : (v>=0 ? '#b83227' : '#1e7e40');
    return 'background:rgba('+rgb+','+a.toFixed(2)+');color:'+txt+';font-weight:600;text-align:center;';
  }}
  function updateExcessMatrix() {{
    var hasWE = DATA.funds.some(function(f){{return !!f.weeklyExcess;}});
    if (!hasWE) {{ document.getElementById('excessMatrixCount').textContent='0 只'; document.querySelector('#tableExcessMatrix thead').innerHTML=''; document.querySelector('#tableExcessMatrix tbody').innerHTML=''; return; }}
    var strat=document.getElementById('excessMatrixStrategy').value, size=document.getElementById('excessMatrixSize').value, search=document.getElementById('excessMatrixSearch').value.toLowerCase();
    var matched=DATA.funds.filter(function(f){{return (strat==='all'||f.strategy===strat)&&(size==='all'||f.size===size)&&(!search||f.company.toLowerCase().indexOf(search)>=0);}});
    var rows=[]; matched.forEach(function(f){{var w=exWinRate(f); if(w) rows.push({{f:f,w:w}});}});
    rows.sort(function(a,b){{ if(b.w.rate!==a.w.rate) return b.w.rate-a.w.rate; return b.w.avg-a.w.avg; }});
    document.getElementById('excessMatrixCount').textContent=rows.length+' 只';
    var dates_local=DATA.dates.map(function(d){{return d.slice(5);}});
    var thead='<tr><th class="sl">排名</th><th class="sl">管理人</th><th class="sl">规模</th><th class="sl">策略</th><th>累计超额</th><th>超额夏普</th><th>周胜率</th><th>正超额周</th>';
    dates_local.forEach(function(d){{thead+='<th>'+d+'</th>';}});thead+='</tr>';
    document.querySelector('#tableExcessMatrix thead').innerHTML=thead;
    var tbody=''; rows.forEach(function(r,i) {{
      var f=r.f, w=r.w, wrPct=(w.rate*100).toFixed(1), wrCls=w.rate>=0.6?'nav-up':(w.rate>=0.4?'':'nav-down');
      var exArr=f.excesses||[], exValid=exArr.filter(function(n){{return n!==null;}}), cumEx=exValid.length?exValid[exValid.length-1]:null;
      var cumHtml=cumEx!==null?'<td class="'+(cumEx>0?'nav-up':'nav-down')+'" style="font-weight:600">'+(cumEx>=0?'+':'')+(cumEx*100).toFixed(2)+'%</td>':'<td style="color:#888">-</td>';
      var we=f.weeklyExcess||[], weValid=we.filter(function(v){{return v!==null;}}), esSharpe=null;
      if(weValid.length>1){{var em=weValid.reduce(function(a,b){{return a+b;}},0)/weValid.length;var esd=Math.sqrt(weValid.reduce(function(s,v){{return s+Math.pow(v-em,2);}},0)/(weValid.length-1));esSharpe=esd>0?em/esd*Math.sqrt(52):null;}}
      var esHtml=esSharpe!==null?'<td class="'+(esSharpe>0?'nav-up':'nav-down')+'" style="font-weight:600">'+esSharpe.toFixed(2)+'</td>':'<td style="color:#888">-</td>';
      tbody+='<tr><td class="sl"><b>'+(i+1)+'</b></td><td class="sl">'+fundLink(f.company,f.strategy)+'</td><td class="sl">'+f.size+'</td><td class="sl">'+f.strategy+'</td>'+cumHtml+esHtml+'<td class="'+wrCls+'" style="font-weight:600">'+wrPct+'%</td><td style="color:#888">'+w.up+'/'+w.total+'</td>';
      dates_local.forEach(function(d,j){{var v=(f.weeklyExcess&&f.weeklyExcess[j]!==undefined)?f.weeklyExcess[j]:null; if(v!==null){{tbody+='<td style="'+exCellStyle(v)+'">'+(v>=0?'+':'')+(v*100).toFixed(2)+'%</td>';}}else{{tbody+='<td style="color:#888">·</td>';}}}});
      tbody+='</tr>';
    }});
    document.querySelector('#tableExcessMatrix tbody').innerHTML=tbody;
    fixStickyLeft('tableExcessMatrix', 8);
  }}


  // Apply sticky left offsets: freeze the first `freezeCount` columns.
  // Defer via rAF and re-try while the table is still hidden: #app starts at
  // display:none behind the password overlay, so the first pass would measure
  // zero-width columns and freeze the wrong number of columns.
      function fixStickyLeft(tableId, freezeCount) {{
    freezeCount = freezeCount || 2;
    var table = document.getElementById(tableId);
    if (!table) return;
    var tries = 0;
    function apply() {{
      var headerCells = table.querySelectorAll('thead tr th');
      var bodyRows = table.querySelectorAll('tbody tr');
      if (!headerCells.length || !bodyRows.length) return;
      if (table.offsetWidth === 0 && tries++ < 120) {{ requestAnimationFrame(apply); return; }}
      var n = Math.min(freezeCount, headerCells.length);
      // Measure natural widths of the columns to be frozen
      var widths = [];
      for (var i = 0; i < n; i++) {{
        var w = headerCells[i].getBoundingClientRect().width;
        widths.push(Math.max(w, 30)); // minimum 30px per column
      }}
      var lefts = [0];
      for (var i = 1; i < n; i++) {{
        lefts.push(Math.round(lefts[i-1] + widths[i-1]));
      }}
      for (var i = 0; i < n; i++) {{
        headerCells[i].classList.add('sl');
        headerCells[i].style.left = lefts[i] + 'px';
        headerCells[i].style.minWidth = widths[i] + 'px';
        headerCells[i].style.zIndex = (n - i + 1);
      }}
      for (var r = 0; r < bodyRows.length; r++) {{
        var cells = bodyRows[r].querySelectorAll('td');
        for (var j = 0; j < n && j < cells.length; j++) {{
          cells[j].classList.add('sl');
          cells[j].style.left = lefts[j] + 'px';
          cells[j].style.minWidth = widths[j] + 'px';
          cells[j].style.zIndex = (n - j);
        }}
      }}
    }}
    requestAnimationFrame(apply);
  }}

  // Export to window for HTML onclick handlers and event proxies
  window.addLine = addLine;
  window.clearLines = clearLines;
  window.drawFundChart = drawFundChart;
  window.updateGridSizes = updateGridSizes;
  window.drawGridChart = drawGridChart;
  window.updateWRTable = updateWRTable;
  window.updateYTDTable = updateYTDTable;
  window.updateRankTable = updateRankTable;
  window.updateRankMatrix = updateRankMatrix;
  window.updateExcessMatrix = updateExcessMatrix;
  window.updateFundPicker = updateFundPicker;

  // Wire events (all through window.xxx to always call latest functions)
  document.getElementById('filterStrategy').addEventListener('change', function(){{ window.updateFundPicker(); }});
  document.getElementById('pickerFund').addEventListener('change', function(){{ extraLines=[]; window.drawFundChart(); }});
  document.getElementById('fundBench').addEventListener('change', function(){{ window.drawFundChart(); }});
  document.getElementById('filterRankStrategy').addEventListener('change', function(){{ syncSizeDropdown(document.getElementById('filterRankSize'), this.value, 'all'); window.updateRankTable(); }});
  document.getElementById('filterRankSize').addEventListener('change', function(){{ window.updateRankTable(); }});
  document.getElementById('searchRank').addEventListener('input', function(){{ window.updateRankTable(); }});
  document.getElementById('gridStrategy').addEventListener('change', function(){{ window.updateGridSizes(); }});
  document.getElementById('gridSize').addEventListener('change', function(){{ window.drawGridChart(); }});
  document.getElementById('gridBench').addEventListener('change', function(){{ window.drawGridChart(); }});
  document.getElementById('gridSearch').addEventListener('input', function(){{ window.drawGridChart(); }});
  document.getElementById('wrWeek').addEventListener('change', function(){{ window.updateWRTable(); }});
  document.getElementById('wrSize').addEventListener('change', function(){{ window.updateWRTable(); }});
  document.getElementById('wrSearch').addEventListener('input', function(){{ window.updateWRTable(); }});
  document.getElementById('ytdStrategy').addEventListener('change', function(){{ syncSizeDropdown(document.getElementById('ytdSize'), this.value, 'all'); window.updateYTDTable(); }});
  document.getElementById('ytdSize').addEventListener('change', function(){{ window.updateYTDTable(); }});
  document.getElementById('ytdSearch').addEventListener('input', function(){{ window.updateYTDTable(); }});
  document.getElementById('wrStrategy').addEventListener('change', function(){{ syncSizeDropdown(document.getElementById('wrSize'), this.value, 'all'); window.updateWRTable(); }});
  document.getElementById('rankMatrixStrategy').addEventListener('change', function(){{ syncSizeDropdown(document.getElementById('rankMatrixSize'), this.value, 'all'); window.updateRankMatrix(); }});
  document.getElementById('rankMatrixSize').addEventListener('change', function(){{ window.updateRankMatrix(); }});
  document.getElementById('rankMatrixSearch').addEventListener('input', function(){{ window.updateRankMatrix(); }});
  document.getElementById('excessMatrixStrategy').addEventListener('change', function(){{ syncSizeDropdown(document.getElementById('excessMatrixSize'), this.value, 'all'); window.updateExcessMatrix(); }});
  document.getElementById('excessMatrixSize').addEventListener('change', function(){{ window.updateExcessMatrix(); }});
  document.getElementById('excessMatrixSearch').addEventListener('input', function(){{ window.updateExcessMatrix(); }});

  // Trigger initial render (fire change events to populate size dropdowns)
  document.getElementById('wrStrategy').dispatchEvent(new Event('change'));
  document.getElementById('ytdStrategy').dispatchEvent(new Event('change'));
  document.getElementById('filterRankStrategy').dispatchEvent(new Event('change'));
  document.getElementById('rankMatrixStrategy').dispatchEvent(new Event('change'));
  document.getElementById('excessMatrixStrategy').dispatchEvent(new Event('change'));
  updateGridSizes();updateFundPicker();updateWRTable();updateYTDTable();
}}

initAll();
function fundLink(c,s){{return '<span class="fund-link" data-company="'+c+'" data-strategy="'+s+'">'+c+'</span>';}}
var productChart1=null,productChart2=null,currentPFund=null;
function showProductDetail(company,strategy){{var f=ABS_DATA.funds.find(function(ff){{return ff.company===company&&ff.strategy===strategy;}});if(!f)return;currentPFund=f;document.getElementById('modalTitle').textContent=f.company+' · '+f.strategy+' · '+f.size;var dates=ABS_DATA.dates,ws=dates.length,selS=document.getElementById('rangeStart'),selE=document.getElementById('rangeEnd');selS.innerHTML='';selE.innerHTML='';dates.forEach(function(d,i){{var opt='<option value="'+i+'">'+d.slice(5)+'</option>';selS.innerHTML+=opt;selE.innerHTML+=opt;}});selS.value=0;selE.value=ws-1;document.getElementById('productModal').classList.add('show');setTimeout(function(){{if(!productChart1){{productChart1=echarts.init(document.getElementById('chartProductNav'));productChart2=echarts.init(document.getElementById('chartProductWeekly'));}}else{{productChart1.resize();productChart2.resize();}}updateProductMetrics();}},50);}}
function closeProductModal(){{document.getElementById('productModal').classList.remove('show');currentPFund=null;}}
function updateProductMetrics(){{var f=currentPFund;if(!f)return;var sI=parseInt(document.getElementById('rangeStart').value),eI=parseInt(document.getElementById('rangeEnd').value);if(eI<sI){{var t=sI;sI=eI;eI=t;}}var dates=ABS_DATA.dates.slice(sI,eI+1),wlabs=ABS_DATA.weekLabels.slice(sI,eI+1),navsR=f.navs.slice(sI,eI+1),excsR=f.excesses.slice(sI,eI+1),wData=[];wlabs.forEach(function(w){{var wd=ABS_DATA.weeklyData[w];if(wd){{var e=wd.find(function(r){{return r.company===f.company&&r.strategy===f.strategy;}});if(e)wData.push(e);}}}});var nW=wData.length,allNavs=navsR.filter(function(n){{return n!==null;}}),allExcs=excsR.filter(function(n){{return n!==null;}}),sNav=navsR.find(function(n){{return n!==null;}})||1,eNav=allNavs.length?allNavs[allNavs.length-1]:sNav,totRet=(eNav/sNav-1)*100,annR=(Math.pow(eNav/sNav,52/Math.max(1,nW))-1)*100,sExc=excsR.find(function(n){{return n!==null;}})||0,eExc=allExcs.length?allExcs[allExcs.length-1]:sExc,totExc=(eExc-sExc)*100,wRets=wData.map(function(w){{return w.weekly_return;}});var meanR=nW>0?wRets.reduce(function(a,b){{return a+b;}},0)/nW:0,variance=nW>0?wRets.reduce(function(sum,r){{return sum+Math.pow(r-meanR,2);}},0)/nW:0,annVol=Math.sqrt(Math.max(0,variance)*52)*100,sharpe=annVol>0?(annR/annVol):0,peak=-Infinity,maxDD=0;navsR.forEach(function(n){{if(n===null)return;if(n>peak)peak=n;var dd=(n-peak)/peak;if(dd<maxDD)maxDD=dd;}});var up=wRets.filter(function(r){{return r>0;}}).length,winR=nW>0?(up/nW*100).toFixed(1):'-',wcPct=(maxDD*100).toFixed(2),upCls=totRet>=0?'nav-up':'nav-down',ddCls=maxDD===0?'nav-up':'nav-down';document.getElementById('modalMetrics').innerHTML='<div class="modal-mcard"><div class="mv '+upCls+'">'+(totRet>=0?'+':'')+totRet.toFixed(2)+'%</div><div class="ml">区间累计收益</div></div><div class="modal-mcard"><div class="mv '+upCls+'">'+(annR>=0?'+':'')+annR.toFixed(2)+'%</div><div class="ml">年化收益</div></div><div class="modal-mcard"><div class="mv '+(totExc>=0?'nav-up':'nav-down')+'">'+(totExc>=0?'+':'')+totExc.toFixed(2)+'%</div><div class="ml">累计超额</div></div><div class="modal-mcard"><div class="mv">'+annVol.toFixed(2)+'%</div><div class="ml">年化波动率</div></div><div class="modal-mcard"><div class="mv '+ddCls+'">'+wcPct+'%</div><div class="ml">最大回撤</div></div><div class="modal-mcard"><div class="mv">'+sharpe.toFixed(2)+'</div><div class="ml">Sharpe</div></div><div class="modal-mcard"><div class="mv">'+winR+'%</div><div class="ml">周胜率</div></div><div class="modal-mcard"><div class="mv">'+nW+'</div><div class="ml">数据周数</div></div>';document.getElementById('rangeInfo').textContent=nW+' 周 ('+dates[0]+' ~ '+dates[dates.length-1]+')';var navData=[];navsR.forEach(function(n,i){{if(n!==null)navData.push([dates[i].slice(5),n]);}});var excData=[];excsR.forEach(function(n,i){{if(n!==null)excData.push([dates[i].slice(5),n]);}});var ts=TS[currentTheme]||TS.dark;productChart1.setOption({{backgroundColor:'transparent',tooltip:{{trigger:'axis',backgroundColor:ts.tbg,borderColor:ts.tbc,textStyle:{{color:ts.ttc}}}},legend:{{bottom:0,textStyle:{{color:ts.alc}}}},grid:{{left:60,right:30,top:20,bottom:40}},xAxis:{{type:'category',data:dates.map(function(d){{return d.slice(5);}}),axisLabel:{{rotate:45,fontSize:10,color:ts.alc}},axisLine:{{lineStyle:{{color:ts.slc}}}},boundaryGap:false}},yAxis:[{{type:'value',scale:true,axisLabel:{{formatter:function(v){{return v.toFixed(3);}},color:ts.alc}},splitLine:{{lineStyle:{{color:ts.slc}}}}}},{{type:'value',scale:true,axisLabel:{{formatter:function(v){{return(v*100).toFixed(1)+'%';}},color:ts.alc}},splitLine:{{show:false}}}}],series:[{{name:'累计净值',type:'line',data:navData,smooth:true,symbol:'circle',symbolSize:4,lineStyle:{{width:3,color:'#d4a050'}},itemStyle:{{color:'#d4a050'}},tooltip:{{valueFormatter:function(v){{return v!=null?v.toFixed(4):'-';}}}}}},{{name:'超额收益',type:'line',yAxisIndex:1,data:excData,smooth:true,symbol:'diamond',symbolSize:4,lineStyle:{{width:2,color:'#60a5fa',type:'dashed'}},itemStyle:{{color:'#60a5fa'}},tooltip:{{valueFormatter:function(v){{return v!=null?(v*100).toFixed(2)+'%':'-';}}}}}}]}},true);var peakExc=-Infinity,ddData=[];excsR.forEach(function(n,i){{if(n!==null){{if(n>peakExc)peakExc=n;ddData.push([dates[i].slice(5),(n-peakExc)*100]);}}}});try{{var ddGrad=typeof echarts!=='undefined'?new echarts.graphic.LinearGradient(0,0,0,1,[{{offset:0,color:'rgba(231,76,60,0.35)'}},{{offset:1,color:'rgba(231,76,60,0.02)'}}]):'rgba(231,76,60,0.15)';productChart2.setOption({{backgroundColor:'transparent',tooltip:{{trigger:'axis',backgroundColor:ts.tbg,borderColor:ts.tbc,textStyle:{{color:ts.ttc}},valueFormatter:function(v){{return v!=null?v.toFixed(2)+'%':'-';}}}},grid:{{left:60,right:30,top:20,bottom:40}},xAxis:{{type:'category',data:dates.map(function(d){{return d.slice(5);}}),axisLabel:{{rotate:45,fontSize:10,color:ts.alc}},axisLine:{{lineStyle:{{color:ts.slc}}}},boundaryGap:false}},yAxis:{{type:'value',max:0,axisLabel:{{formatter:function(v){{return v.toFixed(1)+'%';}},color:ts.alc}},splitLine:{{lineStyle:{{color:ts.slc}}}}}},series:[{{name:'超额回撤',type:'line',data:ddData,smooth:true,symbol:'none',lineStyle:{{width:2,color:'#e74c3c'}},areaStyle:{{color:ddGrad}}}}]}},true);productChart2.resize();}}catch(e){{console.error('productChart2 error:',e);}}}}
document.addEventListener('click',function(e){{if(e.target.id==='productModal')closeProductModal();var el=e.target.closest('.fund-link');if(el)showProductDetail(el.getAttribute('data-company'),el.getAttribute('data-strategy'));}});
// resize: single global listener (registered once at top)
async function checkPw(){{const i=document.getElementById('pwInput');const e=document.getElementById('pwErr');const h=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(i.value));const hex=Array.from(new Uint8Array(h)).map(b=>b.toString(16).padStart(2,'0')).join('');if(hex==='5856077678deae2bfae7a71271e97bb24337ca249bba1175fe1fa36a30d529e4'){{sessionStorage.setItem('cc_auth','1');document.getElementById('pwOverlay').classList.add('hide');document.getElementById('app').style.display='';setTimeout(function(){{cS&&cS.resize();cG&&cG.resize();cF&&cF.resize();}},100)}}else{{e.textContent='密码错误';document.querySelector('.pw-card').classList.add('shake');setTimeout(function(){{document.querySelector('.pw-card').classList.remove('shake')}},400);i.value=''}}}}document.addEventListener('DOMContentLoaded',function(){{if(sessionStorage.getItem('cc_auth')){{document.getElementById('pwOverlay').classList.add('hide');document.getElementById('app').style.display='';setTimeout(function(){{cS&&cS.resize();cG&&cG.resize();cF&&cF.resize();}},100)}}else{{document.getElementById('pwInput').focus()}}document.getElementById('pwInput').addEventListener('keydown',function(ev){{if(ev.key==='Enter')checkPw()}})}})
</script></div>
<div class="modal-overlay" id="productModal">
<div class="modal-content">
<div class="modal-header">
<h2 id="modalTitle"></h2>
<button class="modal-close" onclick="closeProductModal()">✕ 关闭</button>
</div>
<div class="modal-body">
<div class="modal-metrics" id="modalMetrics"></div>
<div class="range-bar">
<label>⏱ 时间范围</label>
<select id="rangeStart" onchange="updateProductMetrics()"></select>
<span style="color:var(--text-muted);font-size:12px">→</span>
<select id="rangeEnd" onchange="updateProductMetrics()"></select>
<span style="color:var(--text-muted);font-size:11px" id="rangeInfo"></span>
</div>
<div class="chart-inline"><div class="chart chart-half" id="chartProductNav"></div><div class="chart chart-half" id="chartProductWeekly"></div></div>
</div>
</div>
</div>
</body></html>"""

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nWritten {OUTPUT_PATH}: {len(html)} chars")

    # Also sync index.html for local opening
    index_path = OUTPUT_PATH.replace("dashboard.html", "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Synced {index_path}: {len(html)} chars")

    # Also sync docs/index.html for GitHub Pages deployment
    docs_path = os.path.join(PROJECT_ROOT, "docs", "index.html")
    os.makedirs(os.path.dirname(docs_path), exist_ok=True)
    with open(docs_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Synced {docs_path}: {len(html)} chars")


if __name__ == "__main__":
    main()
