# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。

## 项目概述

一个量化私募基金业绩数据库平台。从"点睛业绩放送"的周度 Excel 排名数据中提取,计算累计净值(年初=1.0),并提供交互式看板用于策略对比、排名展示与基准叠加。

## 常用命令

```bash
# 完整流程(顺序固定: 先更新基准 → 导入周度 → 生成看板)
make update-data

# 单步执行
make update-benchmark     # CSIndex API → benchmark_nav.json
make import-weekly        # Excel → SQLite (cc_data.sqlite3)
make rebuild-dashboard    # SQLite + benchmark_nav.json → dashboard.html + docs/index.html

# 直接调用脚本(注意使用 python3)
cd backend && python3 scripts/update_benchmark.py
cd backend && python3 scripts/import_weekly_sqlite.py
cd backend && python3 scripts/rebuild_dashboard.py

# 核心计算单测(超额收益/回撤/复利)
make test                 # cd backend && python3 -m pytest

# Lint 检查
cd backend && ruff check .
```

## 架构

### 单一数据通路: SQLite + 自包含 HTML

`cc_data.sqlite3` → `dashboard.html` 是**唯一**的数据通路。周度 Excel 的**正本**保存在 `点睛焱究所/4. 周度业绩排名更新及业绩点评/周度业绩/2026/量化股票/`;`backend/scripts/import_weekly_sqlite.py` 的 `DATA_DIR` 指向项目根的 `data/`,但 `data/` 只是**临时导入工作区**(导入完即清理,`data/*.xlsx` 已被 gitignore)——全量重建时需先把正本复制进 `data/` 再导入。独立的 `dashboard.html`(自包含,约 4MB)将所有数据以 `var DATA = {...}` 的 JSON 形式内嵌,并使用 ECharts 5(CDN 加载)渲染图表。无需服务器 —— 直接用浏览器打开 HTML 文件即可。

> 此前的 PostgreSQL + FastAPI + React 路线已被移除: 它与真实的 SQLite schema 产生了偏离(缺少 `size_category`、没有 `weekly_performances` 模型),且从未真正运行过。在没有先按下文 SQLite 表结构核对 schema 之前,不要重新引入 server/SPA 路线。

### 看板 HTML (`dashboard.html`)

单一自包含文件,包含 8 个板块:
- **① 策略走势 + 基准指数**: 7 条策略平均曲线 + 6 条基准指数线(粗虚线)
- **② 策略净值对比**: 按策略/规模筛选,可叠加选择的基准,展示前 30 只产品
- **③ 周度收益排名**: 按周/策略/规模的交互式表格,带柱状图和分位数
- **④ 今年以来收益排名**: 累计净值与年内累计收益排名
- **⑤ 单基金对比**: 多选产品对比,可叠加基准
- **⑥ 累计净值排名矩阵**(`tableRank`): 产品 × 周累计净值表,左 7 列冻结;超额 tab 下切到累计超额,回撤 tab 下切到最大超额回撤
- **⑦ 收益排名矩阵**(`tableRankMatrix`): 产品 × 周名次排名,按最新名次排序,名次绿(前 5)→红(靠后),左 6 列冻结(三 tab 共用,名次随 tab 数据切换)
- **⑧ 周超额分析矩阵**(`tableExcessMatrix`,仅超额 tab): 产品 × 周单周超额收益,按周超额胜率排序,涨红跌绿,左 6 列冻结

`makeBenchSeries(bname, showSymbol)` 用于创建基准序列。基准数据为日频,但通过 `DATA.dates` 查表重采样为与产品记录日匹配的周度日期(数量随数据动态变化,当前约 29 个)。图表 ①/⑤ 使用 `trigger:'axis'` 提示框(无需 symbol)。图表 ② 使用 `trigger:'item'`(需要 `showSymbol=true`,在基准上显示菱形标记)。

> 三个矩阵(⑥⑦⑧)共用冻结列机制 `fixStickyLeft(tableId, freezeCount)`:`#app` 初始为 `display:none`(密码遮罩),首测会量到零宽列、冻结列数错误,故用 `requestAnimationFrame` 重试到表格可见为止(⑥ 冻结 7 列 / ⑦⑧ 冻结 6 列)。涨跌色统一**中国习惯**:红 = 涨/正,绿 = 跌/负(`.nav-up` = 红 / `.nav-down` = 绿,`.tag.up`/`.tag.down` 同)。

### 关键数据模型(来自 SQLite)

```
fund_companies: id, name, size_category
funds: id, company_id → fund_companies, strategy_type, name (格式: "{公司}-{策略名}")
weekly_performances: id, fund_id → funds, week_label, record_date, rank,
  weekly_return, weekly_excess, ytd_return, ytd_excess, ytd_drawdown,
  ann_return, ann_vol, max_drawdown, sharpe, size_category
  — UNIQUE(fund_id, week_label)
benchmark_index: id, symbol, name
benchmark_index_data: id, index_id → benchmark_index, trade_date, close_price
```

累计净值 = `1.0 + ytd_return`(使用"今年以来收益率"列)。缺失的周度数据留空,不补 1.0。

策略映射:
```
量化选股 → stock_long, 市场中性 → market_neutral, 500指增 → index_500,
1000指增 → index_1000, 300指增 → index_300, 2000指增 → index_2000, A500指增 → index_a500
```

策略与超额收益基准的映射:
```
量化选股 → 中证1000, 市场中性 → 基准=0(超额=绝对收益), 500指增 → 中证500,
1000指增 → 中证1000, 300指增 → 沪深300, 2000指增 → 中证2000, A500指增 → A500
```

公司名规范化(`import_weekly_sqlite.py` 的 `COMPANY_NAME_NORMALIZE`,导入时统一混用名):
```
嘉石大岩 → 大岩资本, 海南进化论 → 进化论资产, 衍盛私募 → 衍盛资产
```
> 导入是增量的(`CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE`),所以**改了任何映射(策略/规模/公司名)都必须删库全量重建**,否则残留旧记录。

### 数据处理流程

1. 正本在 `点睛焱究所/.../量化股票/`(当前 29 个周度 Excel,覆盖 0105 → 0724,每个包含 7 张策略表,列数在 14-17 列之间,布局各异);导入前需复制进 `data/`
2. `backend/scripts/import_weekly_sqlite.py` 解析这些文件,规范化规模分类(`~` → `-`),插入 2025-12-31 基线(净值=1.0),创建 SQLite 数据库
3. `merged_weekly_returns.csv` 导出合并后的时间序列
4. `dashboard.html` 生成器内嵌所有数据 + 基准日频净值序列 + 产品详情弹窗
5. 重建时,`dashboard.html` 会自动复制到 `docs/index.html`,用于 GitHub Pages 部署
6. 基准数据通过 **CSIndex 官网 API** 获取(不是 AKShare):
   - 端点: `https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode={code}&startDate={start}&endDate={end}`
   - 全部 6 个基准指数统一使用此 API,AKShare 的 `stock_zh_index_daily` **不再使用**
   - ⚠️ **中证2000 (932000) 的 AKShare/Sina API 已不可用(返回 null)**,必须用 CSIndex API
   - 指数代码对照: 沪深300→000300, 中证500→000905, 中证800→000906, 中证1000→000852, 中证2000→932000, A500→000510
   - **基准净值归一化**: `benchmark_nav.json` 的 navs 相对 **2025-12-31**(年初基线)归一化(1231=1.0);CSIndex API 返回的是真实点位,补数据时必须按尺度换算(scale = 已知日的归一化值 ÷ 真实值),否则会破坏所有基准计算
   - **第一周超额锚点**: 量化选股第一周(0109)的基准收益 = `NAV(0109)/NAV(20251231) − 1`(锚定年初,不是 /上一周),因为第一周的 `weekly_return` 本身就是从 12-31 起算的 ytd 值;仅 `compute_stock_long_excess` 自算超额受此影响,指增超额取自 Excel、市场中性基准=0,均不受影响
   - **几何超额**: 量化选股超额用几何口径——`ytd_excess = (1+ytd_return)/(1+基准累计) − 1`(基准累计 = `NAV(当周)/NAV(20251231) − 1`),直接基于累计值、自洽;`weekly_excess` 为单周几何 `(1+周收益)/(1+基准周收益) − 1`。不用算术差复利(基准波动时会高估超额,且依赖 `∏(1+weekly_return)=1+ytd_return` 的不成立假设)

### Python 3.9 兼容性

SQLite 导入脚本面向 Python 3.9。必须使用:
- `from __future__ import annotations`
- `Optional[X]` 而非 `X | None`
- 从 `typing` 导入 `List[X]`、`Dict[X, Y]`

### Git / 网络注意事项

- 通过端口 7890 的代理(Clash)访问 GitHub: `git -c http.proxy=http://127.0.0.1:7890`
- 中文数据源(CSIndex API)需直连(不走代理)
- `.gitignore` 排除: `*.sqlite3*`(含 WAL/SHM)、`*.csv`(`data/*.csv` 除外)、`data/*.xlsx`(周度表仅本地保留)、`output/`(分析导出)、`点睛焱究所/`(研究资料仅本地保留)、`/dashboard.html` + `/index.html`(生成的看板,仅本地 —— 只有 `docs/index.html` 被纳入版本控制用于 GitHub Pages)

### 近期新增功能(来自 git log)

- **密码保护**: 看板访问时进行 SHA-256 哈希校验
- **产品详情弹窗**: 点击产品名 → 弹窗展示单产品深度分析(ECharts 在弹窗打开后渲染)
- **2025-12-31 基线**: 所有产品在年初净值 = 1.0,在 SQLite 导入时插入
- **超额收益自算**: 超额收益和超额回撤统一自算(不取自 Excel),基于策略与基准的映射关系
- **动态日期标签**: 看板数据日期从 SQLite 动态读取最新的 `record_date`
- **GitHub Pages 自动同步**: `rebuild_dashboard.py` 自动将 `dashboard.html` 复制到 `docs/index.html`
- **⑦⑧ 两个矩阵**: ⑦ 名次排名矩阵(各周排名,绿前红后)、⑧ 周超额分析矩阵(各周单周超额,按周胜率排序,涨红跌绿),均仅超额 tab 显示
- **冻结列机制**: `fixStickyLeft(tableId, freezeCount)` 通用化(⑥ 冻 7 列 / ⑦⑧ 冻 6 列),用 rAF 重试解决密码遮罩下首测零宽导致的冻结列数错误
- **中国涨跌色**: 涨红跌绿(红 `#e74c3c` / 绿 `#27ae60`),`.nav-up` = 红 / `.nav-down` = 绿
- **公司名合并**: `COMPANY_NAME_NORMALIZE` 在导入时统一混用名(如 衍盛私募 → 衍盛资产)
- **规模↔策略联动筛选**: 选策略后规模下拉按该策略可见规模刷新(`syncSizeDropdown`),且不覆盖用户已选规模
