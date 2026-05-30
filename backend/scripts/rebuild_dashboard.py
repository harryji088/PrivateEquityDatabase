"""
Clean rebuild of dashboard.html with absolute + excess return tabs.
"""

import sqlite3
import json
import math

DB_PATH = "/Users/harryji/Documents/trae_projects/CC/cc_data.sqlite3"
BENCHMARK_PATH = "/Users/harryji/Documents/trae_projects/CC/benchmark_nav.json"
OUTPUT_PATH = "/Users/harryji/Documents/trae_projects/CC/dashboard.html"

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

def build_abs_data(cur):
    """Build absolute return DATA (original structure)."""
    cur.execute("SELECT DISTINCT record_date FROM weekly_performances ORDER BY record_date")
    dates = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT DISTINCT week_label FROM weekly_performances ORDER BY week_label")
    week_labels = [r[0] for r in cur.fetchall()]

    # Week info
    week_info = {}
    for wl in week_labels:
        parts = wl.split("-")
        if len(parts) == 2:
            week_info[wl] = parts[1][:2] + "/" + parts[1][2:]
        else:
            week_info[wl] = wl

    # Funds with NAVs
    cur.execute("""
        SELECT f.id, f.name, fc.name, f.strategy_type, wp.size_category
        FROM weekly_performances wp
        JOIN funds f ON f.id = wp.fund_id
        JOIN fund_companies fc ON fc.id = f.company_id
        GROUP BY f.id
        ORDER BY f.strategy_type, fc.name
    """)
    all_funds = cur.fetchall()

    funds_data = []
    for fid, fname, company, strategy, size_cat in all_funds:
        cur.execute("""
            SELECT week_label, ytd_return FROM weekly_performances
            WHERE fund_id = ? ORDER BY record_date
        """, (fid,))
        nav_map = {r[0]: r[1] for r in cur.fetchall()}

        navs = []
        for wl in week_labels:
            ytd = nav_map.get(wl)
            navs.append(round(1.0 + ytd, 6) if ytd is not None else None)

        funds_data.append({
            "company": company,
            "strategy": STRATEGY_CN.get(strategy, strategy),
            "size": norm_size(size_cat),
            "navs": navs,
        })

    # Strategy average NAVs and sizes
    strategy_navs = {}
    strategy_sizes = {}
    for s_key, s_cn in STRATEGY_CN.items():
        strat_fund_ids = [i for i, (fid, fn, cn, st, sz) in enumerate(all_funds) if st == s_key]
        if not strat_fund_ids:
            continue

        week_vals = {wl: [] for wl in week_labels}
        size_set = set()
        for idx in strat_fund_ids:
            f = funds_data[idx]
            size_set.add(f["size"])
            for j, n in enumerate(f["navs"]):
                if n is not None:
                    week_vals[week_labels[j]].append(n)

        avg_navs = []
        for wl in week_labels:
            vals = week_vals[wl]
            avg_navs.append(round(sum(vals) / len(vals), 6) if vals else None)

        strategy_navs[s_cn] = avg_navs
        strategy_sizes[s_cn] = sorted(size_set, key=lambda x: (
            {"100亿以上": 0, "50~100亿": 1, "20~50亿": 2, "10~20亿": 3, "5~10亿": 4, "0~5亿": 5}.get(x, 99)
        ))

    # Weekly data for ranking table
    weekly_data = {}
    for wl in week_labels:
        cur.execute("""
            SELECT fc.name, f.strategy_type, wp.size_category,
                   wp.weekly_return, wp.weekly_excess
            FROM weekly_performances wp
            JOIN funds f ON f.id = wp.fund_id
            JOIN fund_companies fc ON fc.id = f.company_id
            WHERE wp.week_label = ?
            ORDER BY wp.weekly_return DESC
        """, (wl,))
        week_records = []
        for company, strategy, size_cat, wk_ret, wk_ex in cur.fetchall():
            week_records.append({
                "company": company,
                "strategy": STRATEGY_CN.get(strategy, strategy),
                "size": norm_size(size_cat),
                "weekly_return": round(wk_ret, 6) if wk_ret is not None else None,
                "weekly_excess": round(wk_ex, 6) if wk_ex is not None else None,
            })
        weekly_data[wl] = week_records

    # Benchmark data
    with open(BENCHMARK_PATH, "r") as f:
        bench_data = json.load(f)

    # Strategy-to-benchmark mapping
    strategy_bench = {
        "量化选股": "中证1000", "市场中性": "沪深300", "500指增": "中证500",
        "1000指增": "中证1000", "300指增": "沪深300", "2000指增": "中证2000", "A500指增": "A500",
    }

    return {
        "dates": dates,
        "weekLabels": week_labels,
        "weekInfo": week_info,
        "weeklyData": weekly_data,
        "funds": funds_data,
        "avgNavs": strategy_navs,
        "strategySizes": strategy_sizes,
        "benchData": bench_data,
        "strategyBench": strategy_bench,
    }


def build_excess_data(cur):
    """Build excess return DATA."""
    cur.execute("SELECT DISTINCT record_date FROM weekly_performances ORDER BY record_date")
    dates = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT DISTINCT week_label FROM weekly_performances ORDER BY week_label")
    week_labels = [r[0] for r in cur.fetchall()]

    week_info = {}
    for wl in week_labels:
        parts = wl.split("-")
        if len(parts) == 2:
            week_info[wl] = parts[1][:2] + "/" + parts[1][2:]
        else:
            week_info[wl] = wl

    # Funds with excess data
    cur.execute("""
        SELECT f.id, f.name, fc.name, f.strategy_type, wp.size_category
        FROM weekly_performances wp
        JOIN funds f ON f.id = wp.fund_id
        JOIN fund_companies fc ON fc.id = f.company_id
        WHERE wp.ytd_excess IS NOT NULL
        GROUP BY f.id
        ORDER BY f.strategy_type, fc.name
    """)
    excess_funds = cur.fetchall()

    funds_data = []
    for fid, fname, company, strategy, size_cat in excess_funds:
        cur.execute("""
            SELECT week_label, ytd_excess FROM weekly_performances
            WHERE fund_id = ? AND ytd_excess IS NOT NULL
            ORDER BY record_date
        """, (fid,))
        excess_map = {r[0]: r[1] for r in cur.fetchall()}

        navs = []
        for wl in week_labels:
            ex = excess_map.get(wl)
            navs.append(round(1.0 + ex, 6) if ex is not None else None)

        funds_data.append({
            "company": company,
            "strategy": STRATEGY_CN.get(strategy, strategy),
            "size": norm_size(size_cat),
            "navs": navs,
        })

    # Strategy averages (only 指增 strategies)
    strategy_navs = {}
    strategy_sizes = {}
    for s_key, s_cn in STRATEGY_CN.items():
        if s_key in ("stock_long", "market_neutral"):
            continue

        cur.execute("""
            SELECT f.id FROM weekly_performances wp
            JOIN funds f ON f.id = wp.fund_id
            WHERE f.strategy_type = ? AND wp.ytd_excess IS NOT NULL
            GROUP BY f.id
        """, (s_key,))
        strat_fids = [r[0] for r in cur.fetchall()]
        if not strat_fids:
            continue

        # Map fid -> navs index
        fid_to_idx = {}
        for idx, (fid, fn, cn, st, sz) in enumerate(excess_funds):
            fid_to_idx[fid] = idx

        week_vals = {wl: [] for wl in week_labels}
        size_set = set()
        for fid in strat_fids:
            idx = fid_to_idx.get(fid)
            if idx is None:
                continue
            f = funds_data[idx]
            size_set.add(f["size"])
            for j, n in enumerate(f["navs"]):
                if n is not None:
                    week_vals[week_labels[j]].append(n)

        avg_navs = []
        for wl in week_labels:
            vals = week_vals[wl]
            avg_navs.append(round(sum(vals) / len(vals), 6) if vals else None)

        strategy_navs[s_cn] = avg_navs
        strategy_sizes[s_cn] = sorted(size_set, key=lambda x: (
            {"100亿以上": 0, "50~100亿": 1, "20~50亿": 2, "10~20亿": 3, "5~10亿": 4, "0~5亿": 5}.get(x, 99)
        ))

    # Weekly data for excess
    weekly_data = {}
    for wl in week_labels:
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
            week_records.append({
                "company": company,
                "strategy": STRATEGY_CN.get(strategy, strategy),
                "size": norm_size(size_cat),
                "weekly_return": round(wk_ex, 6) if wk_ex is not None else None,
                "ytd_return": round(ytd_ex, 6) if ytd_ex is not None else None,
            })
        weekly_data[wl] = week_records

    return {
        "dates": dates,
        "weekLabels": week_labels,
        "weekInfo": week_info,
        "weeklyData": weekly_data,
        "funds": funds_data,
        "avgNavs": strategy_navs,
        "strategySizes": strategy_sizes,
    }


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    abs_data = build_abs_data(cur)
    excess_data = build_excess_data(cur)
    conn.close()

    abs_json = json.dumps(abs_data, ensure_ascii=False)
    exc_json = json.dumps(excess_data, ensure_ascii=False)

    print(f"ABS_DATA: {len(abs_json)} chars, {len(abs_data['funds'])} funds, {len(abs_data['avgNavs'])} strategies")
    print(f"EXCESS_DATA: {len(exc_json)} chars, {len(excess_data['funds'])} funds, {len(excess_data['avgNavs'])} strategies")

    # ── Build HTML ──
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>量化私募业绩看板</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f6fa;color:#2c3e50;padding:16px}}
h2{{font-size:18px;margin-bottom:12px;color:#2c3e50;border-left:3px solid #1677ff;padding-left:10px}}
.summary{{display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap}}
.card{{background:#fff;border-radius:8px;padding:16px 24px;box-shadow:0 1px 4px rgba(0,0,0,.08);flex:1;min-width:140px;text-align:center}}
.card .val{{font-size:28px;font-weight:700;color:#1677ff}}
.card .lbl{{font-size:12px;color:#888;margin-top:4px}}
.panel{{background:#fff;border-radius:8px;padding:16px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.chart{{width:100%;height:420px}}
.toolbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}}
.toolbar label{{font-size:13px;color:#555;font-weight:500}}
.toolbar select,.toolbar input{{padding:4px 8px;border:1px solid #d9d9d9;border-radius:4px;font-size:13px;background:#fff}}
.nav-up{{color:#e74c3c;font-weight:600}}
.nav-down{{color:#27ae60;font-weight:600}}
.tag{{padding:2px 8px;border-radius:10px;font-size:12px;font-weight:500}}
.tag.up{{background:#ffeaea;color:#c0392b}}
.tag.down{{background:#e8f8f0;color:#1e8449}}
.rank-table{{width:100%;border-collapse:collapse;font-size:13px}}
.rank-table th{{background:#f0f5ff;padding:8px 6px;border:1px solid #e8e8e8;position:sticky;top:0;z-index:1;white-space:nowrap}}
.rank-table td{{padding:6px;border:1px solid #f0f0f0;text-align:center;white-space:nowrap}}
.rank-table tr:hover td{{background:#fafafa}}
.tabs{{display:flex;gap:0;margin-bottom:16px;border-bottom:2px solid #e8e8e8}}
.tab-btn{{padding:10px 24px;font-size:15px;font-weight:600;cursor:pointer;border:none;background:none;color:#999;border-bottom:3px solid transparent;margin-bottom:-2px;transition:all .2s}}
.tab-btn:hover{{color:#1677ff}}
.tab-btn.active{{color:#1677ff;border-bottom-color:#1677ff}}
</style></head><body>
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px"><h1 style="font-size:22px;color:#1a1a2e;margin:0">📊 量化私募业绩看板</h1><span style="color:#999;font-size:12px">数据来源：点睛业绩放送 · 更新至2026-05-22</span></div>
<div class="tabs">
  <button class="tab-btn active" id="tabAbs" onclick="switchTab('abs')">📈 绝对收益</button>
  <button class="tab-btn" id="tabExc" onclick="switchTab('excess')">📊 超额收益</button>
</div>
<div class="summary">
<div class="card"><div class="val" id="totalFunds">-</div><div class="lbl">产品总数</div></div>
<div class="card"><div class="val" id="avgNav">-</div><div class="lbl">平均累计净值</div></div>
<div class="card"><div class="val" id="bestNav">-</div><div class="lbl">最高累计净值</div></div>
<div class="card"><div class="val" id="upPct">-</div><div class="lbl">正收益占比</div></div>
<div class="card"><div class="val" id="dataWeeks">-</div><div class="lbl">数据周数</div></div>
</div>
<div class="panel"><h2 id="hdr-strategy">① 策略走势 + 基准指数</h2><div class="chart" id="chartStrategy"></div></div>
<div class="panel"><h2>② 策略净值对比</h2><div class="toolbar"><label>策略</label><select id="gridStrategy"><option value="">请选择</option></select><label>规模</label><select id="gridSize"><option value="all">全部规模</option></select><label id="lblGridBench">基准线</label><select id="gridBench" style="width:140px;"><option value="">无基准线</option></select><span style="color:#888;font-size:12px" id="gridCount"></span></div><div class="chart" id="chartGrid"></div></div>
<div class="panel"><h2>③ 周度收益排名</h2><div class="toolbar"><label>周</label><select id="wrWeek"></select><label>策略</label><select id="wrStrategy"><option value="all">全部策略</option></select><label>规模</label><select id="wrSize"><option value="all">全部规模</option></select><span style="color:#888;font-size:12px" id="wrCount"></span></div><div style="overflow-x:auto;max-height:600px;overflow-y:auto;"><table class="rank-table" id="tableWR"><thead></thead><tbody></tbody></table></div></div>
<div class="panel"><h2>④ 今年以来收益排名</h2><div class="toolbar"><label>策略</label><select id="ytdStrategy"><option value="all">全部策略</option></select><label>规模</label><select id="ytdSize"><option value="all">全部规模</option></select><span style="color:#888;font-size:12px" id="ytdCount"></span></div><div style="overflow-x:auto;max-height:600px;overflow-y:auto;"><table class="rank-table" id="tableYTD"><thead></thead><tbody></tbody></table></div></div>
<div class="panel"><h2>⑤ 单基金对比</h2><div class="toolbar"><label>策略</label><select id="filterStrategy"><option value="all">全部策略</option></select><label>基金</label><select id="pickerFund" style="width:300px;"></select><button onclick="window.addLine()" style="padding:4px 12px;">+对比</button><button onclick="window.clearLines()" style="padding:4px 12px;">清除</button><label id="lblFundBench">基准线</label><select id="fundBench" style="width:140px;"><option value="">无基准线</option></select></div><div class="chart" id="chartFund"></div></div>
<div class="panel"><h2>⑥ 累计净值排名矩阵</h2><div class="toolbar"><label>策略</label><select id="filterRankStrategy"><option value="all">全部策略</option></select><input type="text" id="searchRank" placeholder="搜索管理人..." style="width:180px;"></div><div style="overflow-x:auto;max-height:600px;overflow-y:auto;"><table class="rank-table" id="tableRank"><thead></thead><tbody></tbody></table></div></div>
<script>
var ABS_DATA = {abs_json};
var EXCESS_DATA = {exc_json};
var DATA = ABS_DATA;
var IS_EXCESS = false;

var COLORS = ["#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6","#1abc9c","#e67e22","#34495e","#e91e63","#00bcd4","#ff5722","#795548"];
var BENCH_COLORS = {{"沪深300":"#e74c3c","中证500":"#f39c12","中证800":"#9b59b6","中证1000":"#3498db","中证2000":"#1abc9c","A500":"#e67e22"}};
var SIZE_ORDER = ['100亿以上','50~100亿','20~50亿','10~20亿','5~10亿','0~5亿'];

var cS = null, cG = null, cF = null, extraLines = [];

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

  IS_EXCESS = (tab === 'excess');
  DATA = IS_EXCESS ? EXCESS_DATA : ABS_DATA;

  document.getElementById('tabAbs').className = IS_EXCESS ? 'tab-btn' : 'tab-btn active';
  document.getElementById('tabExc').className = IS_EXCESS ? 'tab-btn active' : 'tab-btn';

  // Show/hide benchmark UI (only the label+select, not the entire toolbar)
  var benchDisplay = IS_EXCESS ? 'none' : '';
  document.getElementById('lblGridBench').style.display = benchDisplay;
  document.getElementById('gridBench').style.display = benchDisplay;
  document.getElementById('lblFundBench').style.display = benchDisplay;
  document.getElementById('fundBench').style.display = benchDisplay;

  // Update section header
  document.getElementById('hdr-strategy').textContent = IS_EXCESS ? '① 策略超额走势' : '① 策略走势 + 基准指数';

  initAll();
}}

function initAll() {{
  // Reset dropdowns with default options
  ['filterStrategy','filterRankStrategy','wrStrategy','ytdStrategy'].forEach(function(id) {{
    document.getElementById(id).innerHTML = '<option value="all">全部策略</option>';
  }});
  document.getElementById('gridStrategy').innerHTML = '<option value="">请选择</option>';
  ['gridBench','fundBench'].forEach(function(id) {{
    var sel = document.getElementById(id); sel.innerHTML = '<option value="">无基准线</option>';
  }});

  var dates = DATA.dates.map(function(d){{return d.slice(5);}});
  var strats = Object.keys(DATA.avgNavs);
  var benchNames = DATA.benchData ? Object.keys(DATA.benchData) : [];

  // Strategy dropdowns
  ['filterStrategy','filterRankStrategy','gridStrategy','wrStrategy','ytdStrategy'].forEach(function(id) {{
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
  var finals = []; DATA.funds.forEach(function(f){{var v=f.navs.filter(function(n){{return n!==null;}});if(v.length)finals.push(v[v.length-1]);}});
  document.getElementById('totalFunds').textContent = DATA.funds.length;
  document.getElementById('avgNav').textContent = (finals.reduce(function(a,b){{return a+b;}},0)/finals.length).toFixed(4);
  document.getElementById('bestNav').textContent = Math.max.apply(null,finals).toFixed(4);
  document.getElementById('upPct').textContent = (finals.filter(function(v){{return v>1;}}).length/finals.length*100).toFixed(0)+'%';
  document.getElementById('dataWeeks').textContent = DATA.dates.length;

  // 1. Strategy chart
  cS = echarts.init(document.getElementById('chartStrategy'));
  var sSeries=[], ci=0;
  Object.keys(DATA.avgNavs).forEach(function(s) {{
    var d=[]; DATA.avgNavs[s].forEach(function(n,j){{if(n!==null)d.push([dates[j],n]);}});
    sSeries.push({{name:s,type:'line',data:d,smooth:true,symbol:'circle',symbolSize:3,lineStyle:{{width:2,color:COLORS[ci%COLORS.length]}}}});
    ci++;
  }});
  benchNames.forEach(function(b){{ var bs = makeBenchSeries(b); if(bs) sSeries.push(bs); }});
  cS.setOption({{tooltip:{{trigger:'axis'}},legend:{{bottom:0,type:'scroll'}},grid:{{left:50,right:30,top:20,bottom:40}},xAxis:{{type:'category',data:dates,axisLabel:{{rotate:45,fontSize:10}},boundaryGap:false}},yAxis:{{type:'value',min:IS_EXCESS?undefined:0.82,scale:IS_EXCESS,axisLabel:{{formatter:function(v){{return v.toFixed(3);}}}}}},series:sSeries}});
  window.addEventListener('resize',function(){{cS.resize();}});

  // 2. Grid chart
  cG = echarts.init(document.getElementById('chartGrid'));
  function updateGridSizes() {{
    var strat=document.getElementById('gridStrategy').value, sel=document.getElementById('gridSize');
    sel.innerHTML='<option value="all">全部规模</option>';
    if(strat&&DATA.strategySizes[strat]){{DATA.strategySizes[strat].forEach(function(sz){{sel.innerHTML+='<option value="'+sz+'">'+sz+'</option>';}});}}
    drawGridChart();
  }}
  function drawGridChart() {{
    var strat=document.getElementById('gridStrategy').value, size=document.getElementById('gridSize').value, bench=document.getElementById('gridBench').value, countEl=document.getElementById('gridCount');
    if(!strat){{cG.setOption({{title:{{text:'请选择策略',left:'center',top:'center'}}}},true);countEl.textContent='';return;}}
    var matched=DATA.funds.filter(function(f){{return f.strategy===strat&&(size==='all'||f.size===size);}});
    matched.sort(function(a,b){{var va=a.navs.filter(function(n){{return n!==null;}}),vb=b.navs.filter(function(n){{return n!==null;}});return (vb[vb.length-1]||0)-(va[va.length-1]||0);}});
    countEl.textContent=matched.length+' 只'; var display=matched.slice(0,30), series=[];
    display.forEach(function(f,i){{var d=[];f.navs.forEach(function(n,j){{if(n!==null)d.push([dates[j],n]);}});series.push({{name:f.company+' ['+f.size+']',type:'line',data:d,smooth:true,symbol:'circle',symbolSize:3,lineStyle:{{width:1.5,color:COLORS[i%COLORS.length]}},emphasis:{{focus:'series',lineStyle:{{width:3}},symbolSize:6}}}});}});
    if(bench&&!IS_EXCESS){{ var bs = makeBenchSeries(bench, true); if(bs) series.push(bs); }}
    cG.setOption({{tooltip:{{trigger:'item',formatter:function(p){{return '<b>'+p.seriesName+'</b><br/>'+p.value[0]+'<br/>净值: <b>'+p.value[1].toFixed(4)+'</b>';}}}},legend:{{show:false}},grid:{{left:50,right:30,top:20,bottom:30}},xAxis:{{type:'category',data:dates,axisLabel:{{rotate:45,fontSize:10}},boundaryGap:false}},yAxis:{{type:'value',scale:true,axisLabel:{{formatter:function(v){{return v.toFixed(3);}}}}}},series:series}},true);
  }}
  window.addEventListener('resize',function(){{cG.resize();}});

  // 3. Weekly ranking
  var wrWeekSel=document.getElementById('wrWeek');
  wrWeekSel.innerHTML = '';
  DATA.weekLabels.forEach(function(wl){{var info=DATA.weekInfo[wl]||wl;wrWeekSel.innerHTML+='<option value="'+wl+'">'+wl+' ('+info+')</option>';}});
  wrWeekSel.value=DATA.weekLabels[DATA.weekLabels.length-1];
  function updateWRTable() {{
    var week=document.getElementById('wrWeek').value, strat=document.getElementById('wrStrategy').value, size=document.getElementById('wrSize').value, countEl=document.getElementById('wrCount');
    var data=DATA.weeklyData[week]||[], filtered=data.filter(function(r){{if(strat!=='all'&&r.strategy!==strat)return false;if(size!=='all'&&r.size!==size)return false;return true;}});
    var n=filtered.length;filtered.sort(function(a,b){{return b.weekly_return-a.weekly_return;}}); filtered.forEach(function(r,i){{r.pct=n>1?Math.round((n-i)/n*100):100;}}); countEl.textContent=n+' 条';
    var maxAbs=0;filtered.forEach(function(r){{maxAbs=Math.max(maxAbs,Math.abs(r.weekly_return));}});
    if (IS_EXCESS) {{
      document.querySelector('#tableWR thead').innerHTML='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>周超额</th><th>收益柱</th><th>分位</th></tr>';
    }} else {{
      document.querySelector('#tableWR thead').innerHTML='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>周收益</th><th>周超额</th><th>收益柱</th><th>分位</th></tr>';
    }}
    var tbody='';filtered.forEach(function(r,i){{var retPct=(r.weekly_return*100).toFixed(2),isUp=r.weekly_return>=0,cls=isUp?'nav-up':'nav-down',barW=maxAbs>0?Math.abs(r.weekly_return)/maxAbs*100:100,barColor=isUp?'#e74c3c':'#27ae60';
      if(IS_EXCESS){{
        tbody+='<tr><td><b>'+(i+1)+'</b></td><td>'+r.company+'</td><td>'+r.strategy+'</td><td>'+r.size+'</td><td class="'+cls+'">'+(isUp?'+':'')+retPct+'%</td><td style="width:180px;"><span style="display:inline-block;width:'+barW+'%;height:12px;background:'+barColor+';border-radius:3px;vertical-align:middle;"></span></td><td>'+r.pct+'%</td></tr>';
      }}else{{
        var exPct=r.weekly_excess!==null?(r.weekly_excess*100).toFixed(2):'-';
        tbody+='<tr><td><b>'+(i+1)+'</b></td><td>'+r.company+'</td><td>'+r.strategy+'</td><td>'+r.size+'</td><td class="'+cls+'">'+(isUp?'+':'')+retPct+'%</td><td class="'+(r.weekly_excess!==null&&r.weekly_excess>=0?'nav-up':'nav-down')+'">'+(r.weekly_excess!==null?(r.weekly_excess>=0?'+':'')+exPct+'%':'-')+'</td><td style="width:180px;"><span style="display:inline-block;width:'+barW+'%;height:12px;background:'+barColor+';border-radius:3px;vertical-align:middle;"></span></td><td>'+r.pct+'%</td></tr>';
      }}
    }});
    document.querySelector('#tableWR tbody').innerHTML=tbody;
  }}

  // 4. YTD ranking
  function updateYTDTable() {{
    var strat=document.getElementById('ytdStrategy').value, size=document.getElementById('ytdSize').value, countEl=document.getElementById('ytdCount');
    var filtered=DATA.funds.filter(function(f){{if(strat!=='all'&&f.strategy!==strat)return false;if(size!=='all'&&f.size!==size)return false;return true;}});
    var rows=filtered.map(function(f){{var v=f.navs.filter(function(n){{return n!==null;}});var latest=v.length?v[v.length-1]:null;return{{company:f.company,strategy:f.strategy,size:f.size,nav:latest,ytd:latest!==null?latest-1:null,first:v.length?v[0]:null,weeks:v.length}};}}).filter(function(r){{return r.nav!==null;}}).sort(function(a,b){{return b.nav-a.nav;}});
    var n=rows.length;rows.forEach(function(r,i){{r.pct=n>1?Math.round((n-i)/n*100):100;}}); countEl.textContent=n+' 条';
    var maxAbs=0;rows.forEach(function(r){{maxAbs=Math.max(maxAbs,Math.abs(r.ytd));}});
    if (IS_EXCESS) {{
      document.querySelector('#tableYTD thead').innerHTML='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>超额净值</th><th>YTD超额</th><th>收益柱</th><th>分位</th><th>覆盖</th></tr>';
    }} else {{
      document.querySelector('#tableYTD thead').innerHTML='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>累计净值</th><th>YTD收益</th><th>收益柱</th><th>分位</th><th>覆盖</th></tr>';
    }}
    var tbody='';rows.forEach(function(r,i){{var ytdPct=(r.ytd*100).toFixed(2),isUp=r.ytd>=0,cls=isUp?'nav-up':'nav-down',barW=maxAbs>0?Math.abs(r.ytd)/maxAbs*100:100,barColor=isUp?'#e74c3c':'#27ae60';tbody+='<tr><td><b>'+(i+1)+'</b></td><td>'+r.company+'</td><td>'+r.strategy+'</td><td>'+r.size+'</td><td class="'+cls+'">'+r.nav.toFixed(4)+'</td><td class="'+cls+'">'+(isUp?'+':'')+ytdPct+'%</td><td style="width:120px;"><span style="display:inline-block;width:'+barW+'%;height:12px;background:'+barColor+';border-radius:3px;vertical-align:middle;"></span></td><td>'+r.pct+'%</td><td>'+r.weeks+'/'+DATA.dates.length+'</td></tr>';}});
    document.querySelector('#tableYTD tbody').innerHTML=tbody;
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
    allVals.forEach(function(val,i){{var parts=val.split('|'),name=parts[0],strat=parts.slice(1).join('|');var f=DATA.funds.find(function(f){{return f.company===name&&f.strategy===strat;}});if(!f)return;var d=[];f.navs.forEach(function(n,j){{if(n!==null)d.push([dates[j],n]);}});series.push({{name:name+'('+strat+')',type:'line',data:d,smooth:true,symbol:'circle',symbolSize:5,lineStyle:{{width:3,color:COLORS[i%COLORS.length]}}}});}});
    if(bench&&!IS_EXCESS){{var bs=makeBenchSeries(bench);if(bs)series.push(bs);}}
    cF.setOption({{tooltip:{{trigger:'axis'}},legend:{{bottom:0,type:'scroll'}},grid:{{left:50,right:30,top:20,bottom:40}},xAxis:{{type:'category',data:dates,axisLabel:{{rotate:45,fontSize:10}},boundaryGap:false}},yAxis:{{type:'value',scale:true,axisLabel:{{formatter:function(v){{return v.toFixed(3);}}}}}},series:series}},true);
  }}
  window.addEventListener('resize',function(){{cF.resize();}});

  // 6. Ranking matrix
  function updateRankTable() {{
    var strat=document.getElementById('filterRankStrategy').value, search=document.getElementById('searchRank').value.toLowerCase();
    var funds=DATA.funds.filter(function(f){{return strat==='all'||f.strategy===strat;}}).filter(function(f){{return !search||f.company.toLowerCase().indexOf(search)>=0;}}).map(function(f){{var v=f.navs.filter(function(n){{return n!==null;}});return{{company:f.company,strategy:f.strategy,navs:f.navs,size:f.size,final:v.length?v[v.length-1]:null,first:v.length?v[0]:null,weeks:v.length}};}}).filter(function(f){{return f.final!==null;}}).sort(function(a,b){{return b.final-a.final;}});
    var dates_local = DATA.dates.map(function(d){{return d.slice(5);}});
    var thead='<tr><th>排名</th><th>管理人</th><th>策略</th><th>规模</th><th>最新净值</th><th>变动</th><th>覆盖</th>';
    dates_local.forEach(function(d){{thead+='<th>'+d+'</th>';}});thead+='</tr>';
    document.querySelector('#tableRank thead').innerHTML=thead;
    var tbody='';funds.slice(0,100).forEach(function(f,i){{var ch=f.final!==null&&f.first!==null?f.final-f.first:null,chHtml='-';if(ch!==null){{var cls=ch>0?'up':'down';chHtml='<span class="tag '+cls+'">'+(ch>=0?'+':'')+(ch*100).toFixed(1)+'%</span>';}}tbody+='<tr><td><b>'+(i+1)+'</b></td><td>'+f.company+'</td><td>'+f.strategy+'</td><td>'+f.size+'</td><td class="'+(f.final>=1?'nav-up':'nav-down')+'">'+f.final.toFixed(4)+'</td><td>'+chHtml+'</td><td>'+f.weeks+'/'+DATA.dates.length+'</td>';dates_local.forEach(function(d,j){{var n=f.navs[j];tbody+=n!==null?'<td style="color:'+(n>=1?'#e74c3c':'#27ae60')+'">'+n.toFixed(4)+'</td>':'<td style="color:#ccc">·</td>';}});tbody+='</tr>';}});
    document.querySelector('#tableRank tbody').innerHTML=tbody;
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
  window.updateFundPicker = updateFundPicker;

  // Wire events (all through window.xxx to always call latest functions)
  document.getElementById('filterStrategy').addEventListener('change', function(){{ window.updateFundPicker(); }});
  document.getElementById('pickerFund').addEventListener('change', function(){{ extraLines=[]; window.drawFundChart(); }});
  document.getElementById('fundBench').addEventListener('change', function(){{ window.drawFundChart(); }});
  document.getElementById('filterRankStrategy').addEventListener('change', function(){{ window.updateRankTable(); }});
  document.getElementById('searchRank').addEventListener('input', function(){{ window.updateRankTable(); }});
  document.getElementById('gridStrategy').addEventListener('change', function(){{ window.updateGridSizes(); }});
  document.getElementById('gridSize').addEventListener('change', function(){{ window.drawGridChart(); }});
  document.getElementById('gridBench').addEventListener('change', function(){{ window.drawGridChart(); }});
  document.getElementById('wrWeek').addEventListener('change', function(){{ window.updateWRTable(); }});
  document.getElementById('wrSize').addEventListener('change', function(){{ window.updateWRTable(); }});
  document.getElementById('ytdStrategy').addEventListener('change', function(){{ var s=this.value, sel=document.getElementById('ytdSize'); sel.innerHTML='<option value=\"all\">全部规模</option>'; if(s!=='all'&&DATA.strategySizes[s]){{DATA.strategySizes[s].forEach(function(sz){{sel.innerHTML+='<option value=\"'+sz+'\">'+sz+'</option>';}});}} else if(s==='all'){{SIZE_ORDER.forEach(function(sz){{sel.innerHTML+='<option value=\"'+sz+'\">'+sz+'</option>';}});}} window.updateYTDTable(); }});
  document.getElementById('ytdSize').addEventListener('change', function(){{ window.updateYTDTable(); }});
  document.getElementById('wrStrategy').addEventListener('change', function(){{ var s=this.value, sel=document.getElementById('wrSize'); sel.innerHTML='<option value=\"all\">全部规模</option>'; if(s!=='all'&&DATA.strategySizes[s]){{DATA.strategySizes[s].forEach(function(sz){{sel.innerHTML+='<option value=\"'+sz+'\">'+sz+'</option>';}});}} else if(s==='all'){{SIZE_ORDER.forEach(function(sz){{sel.innerHTML+='<option value=\"'+sz+'\">'+sz+'</option>';}});}} window.updateWRTable(); }});

  // Trigger initial render (fire change events to populate size dropdowns)
  document.getElementById('wrStrategy').dispatchEvent(new Event('change'));
  document.getElementById('ytdStrategy').dispatchEvent(new Event('change'));
  updateGridSizes();updateFundPicker();updateRankTable();updateWRTable();updateYTDTable();
}}

initAll();
</script></body></html>"""

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nWritten {OUTPUT_PATH}: {len(html)} chars")


if __name__ == "__main__":
    main()
