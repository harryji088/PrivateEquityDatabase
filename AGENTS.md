# AGENTS.md

本文件为 Codex (Codex.ai/code) 在本仓库中工作时提供指引。

## 项目概述

一个量化私募基金业绩数据库平台。从"点睛业绩放送"的周度 Excel 排名数据中提取,计算累计净值(年初=1.0),并提供交互式看板与离线量化指增周报。

## 私募净值口令约定

- 用户说“更新净值”：处理 `inbox/` 内的净值截图，识别并核对后写入 `Private_NAV/私募净值.xlsx`；按 `Private_NAV/WORKFLOW.md` 完成预检、备份和核验。
- 用户说“发送净值”：以收到口令的时间为截止点，汇总并发送此前 **1 小时内实际写入** `Private_NAV/私募净值.xlsx` 的全部新增净值。只认成功执行 `--apply` 的写库记录，不把预检报告、重复项、待复核项或之后已撤销/更正的错误记录纳入附件；多次写入需合并并按“基金名称 + 净值日期”去重。发送前核对当前净值库、生成一份窗口汇总附件并先 dry-run，收件人为 `harryji088@163.com`。
- 用户说“发送邮箱”：将最近一次实际更新生成的 `Private_NAV/output/新增净值_*.xlsx` 发送至 `harryji088@163.com`。先 dry-run 核对后再投递。
- 截图批次 CSV 仅是过程文件。确认净值库已更新、汇总已生成后，清理本次生成的 `Private_NAV/batch_*.csv`；不要清理用户手工提供的输入文件。

## 常用命令

```bash
# 完整流程(顺序固定: 先更新基准 → 导入周度 → 生成看板)
make update-data

# 完整流程 + V2A 风格缓存 + 量化指增周报
make update-all

# 单步执行
make update-benchmark     # CSIndex API → benchmark_nav.json
make import-weekly        # Excel → SQLite (cc_data.sqlite3)
make rebuild-dashboard    # SQLite + benchmark_nav.json → dashboard.html + docs/index.html
make update-style         # CSIndex API → style_index_nav.json
make weekly-report-validate  # 只读校验，不生成周报
make weekly-report        # 生成 facts JSON + Markdown 周报

# 直接调用脚本(注意使用 python3)
cd backend && python3 scripts/update_benchmark.py
cd backend && python3 scripts/import_weekly_sqlite.py
cd backend && python3 scripts/rebuild_dashboard.py

# 后端单测（含 V2A、Alpha 热力图边界与更新原子性）
make test                 # cd backend && python3 -m pytest

# Lint 检查
cd backend && python3 -m ruff check .
```

## 架构

### 看板主数据通路: SQLite + 自包含 HTML

`cc_data.sqlite3` → `dashboard.html` 是看板的**唯一**数据通路。周度 Excel 的**正本**保存在 `点睛焱究所/4. 周度业绩排名更新及业绩点评/周度业绩/2026/量化股票/`;`backend/scripts/import_weekly_sqlite.py` 的 `DATA_DIR` 指向项目根的 `data/`,但 `data/` 只是**临时导入工作区**(导入完即清理,`data/*.xlsx` 已被 gitignore)——全量重建时需先把正本复制进 `data/` 再导入。独立的 `dashboard.html`(自包含,约 4MB)将所有数据以 `var DATA = {...}` 的 JSON 形式内嵌,并使用 ECharts 5(CDN 加载)渲染图表。无需服务器 —— 直接用浏览器打开 HTML 文件即可。

量化指增周报是独立的只读分析通路：`cc_data.sqlite3 + benchmark_nav.json + style_index_nav.json + config/*.yaml` → `report_facts.json` → Markdown 周报。生成周报不会联网、更新数据库或重建 Dashboard；事实计算与文字渲染必须分离，Markdown 不得重新计算指标。

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

`makeBenchSeries(bname, showSymbol)` 用于创建基准序列。基准数据为日频,但通过 `DATA.dates` 查表重采样为与产品记录日匹配的周度日期(数量随数据动态变化,当前 35 个)。图表 ①/⑤ 使用 `trigger:'axis'` 提示框(无需 symbol)。图表 ② 使用 `trigger:'item'`(需要 `showSymbol=true`,在基准上显示菱形标记)。

> 三个矩阵(⑥⑦⑧)共用冻结列机制 `fixStickyLeft(tableId, freezeCount)`:`#app` 初始为 `display:none`(密码遮罩),首测会量到零宽列、冻结列数错误,故用 `requestAnimationFrame` 重试到表格可见为止(⑥ 冻结 7 列 / ⑦⑧ 冻结 6 列)。涨跌色统一**中国习惯**:红 = 涨/正,绿 = 跌/负(`.nav-up` = 红 / `.nav-down` = 绿,`.tag.up`/`.tag.down` 同)。

### 关键数据模型(来自 SQLite)

```
fund_companies: id, name, size_category
funds: id, company_id → fund_companies, strategy_type, name (格式: "{公司}-{策略名}")
weekly_performances: id, fund_id → funds, week_label, record_date, rank,
  weekly_return, weekly_excess, ytd_return, ytd_excess, ytd_drawdown,
  ytd_excess_drawdown, ann_return, ann_vol, max_drawdown, sharpe, size_category
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

1. 正本在 `点睛焱究所/.../量化股票/`(当前覆盖 0105 → 0911,每个包含 7 张策略表,列数在 14-17 列之间,布局各异);导入前需复制进 `data/`
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

### 量化指增周报与 V2A 风格层

- 周报范围固定为 300、A500、500、1000、2000 指增，模板排序也固定为该顺序；当前重点管理人为衍复、孝庸、平方和、顽岩、华年。
- V2A 使用 12 条 CSIndex 价格指数日线构造 10 个风格代理，覆盖大小盘、成长/价值、动量、行业中性低波和红利。
- 风格收益差口径：分别计算多头腿与对照腿在窗口起止点的累计收益，再取 `long_return - short_return`；不得累加单周差值，也不得称为产品几何超额。
- 本周首期从上一年 12 月 31 日锚定；取值只允许向报告日之前回看，严禁使用未来数据。
- `style.max_staleness_days=4`：任一端点滞后超过 4 个自然日即数据不完整；正长度窗口若没有新增指数观测，也必须判为不完整，不能输出 0%“持平”。
- `style.neutral_spread_threshold=0.0005`：绝对收益差不超过 0.05% 视为中性，不触发占优、反转或连续方向。
- `alpha_heatmap` 按最近 12 个真实 `record_date` 逐周重算管理人横截面；主指标为 `median_weekly_excess`，辅助指标为 `positive_excess_ratio`，缺失值不按 0，样本门槛复用 `report.min_sample_size`。
- 原有 `weeks_4/weeks_12 cumulative_excess` 是单管理人滚动累计后再做横截面统计；`alpha_heatmap` 是每周横截面独立统计。两种粒度不得混用，renderer 只能读取预计算 facts。
- 管理规模分析必须读取当期 `weekly_performances.size_category`，统一 `-`/`~` 后保留六档原始统计；正文分组由 `size_groups` 配置决定。未知规模只计入数据质量，不进入大中小组比较。
- 规模效应只描述当周横截面：每组有效周超额样本至少 5 个，且合格组中位数极差至少 0.20 个百分点，才可输出 `meaningful`；不得推断长期或因果关系。
- 类别结论只有在该维度**全部配置代理均可用且同向**时才能输出占优/不占优；部分缺失必须显示覆盖数；“短线反转”只表示本周和近 4 周方向相反，不代表趋势确认。
- `style_index_nav.json` 的默认路径来自 `config/weekly_report.yaml` 的 `style.data_path`。加载时必须校验 label、Wind 代码、CSIndex 代码、日期有序且唯一。
- `update_style_indices.py` 默认任一指数失败都不覆盖正式缓存；所有指数更新、完整性、身份与新鲜度校验通过后才原子替换。`--allow-partial` 只允许使用仍然完整、身份正确且新鲜的旧缓存作为失败项回退。
- 同日期周报默认禁止覆盖；只有用户明确要求重生成时使用 `--overwrite`。产物位于 `data/derived/weekly/{日期}/` 和 `reports/weekly/{日期}.md`。

### 点睛焱究所 IMA 知识库更新("更新点睛")

周度 Excel 的正本来自 IMA"点睛焱究所"知识库(`fgp_0fLfUt99hoCcbsW1OPPXIrezZEstzWpniCHhNR8=`)。"更新点睛"= 检查该知识库有无新内容并下载到本地 `点睛焱究所/`。工具在 `scripts/ima/`(`kb_walk.cjs` 遍历 / `kb_download.sh` 下载 / `kb_sync.sh` 比对),凭证在 `~/.config/ima/{client_id,api_key}`,9 个模块的 folder_id 表与已知坑见 `scripts/ima/README.md`。

**检查策略(差异化)**:
- **模块4"周度业绩排名"**(root `folder_7352341879618812`,周度子夹 `folder_7354341090423503`):只列**顶层**看有无新周文件夹(如 `0803-0807`)出现,**不递归遍历** `2025/` 等历史子夹;发现新周后再下钻该周文件夹取 4 份策略 Excel,分别落到 `点睛焱究所/4.../周度业绩/2026/{量化股票,主观多头,CTA,宏观}/`。
- **其余 8 模块**:常规全量递归比对(扁平,安全)。
- 原因:全量递归模块4历史归档树极易耗尽 `get_knowledge_list` 日限额 `220021`(跨天才重置);浅层 1-2 次 API 即可发现新周。"只看顶层"**仅限模块4**。

下载用 `get_media_info` 取签名 URL → `curl -sL`(xlsx 校验 `PK`、pdf 校验 `%PDF`)。`media_type=11` 笔记无下载链接;遇 `220030`(文件级失败)是 IMA 端问题、需在 IMA 客户端处理,非配额耗尽。

**收尾**: 每次更新结束后同步更新 `点睛.md`(下载进度清单)——更新各模块远端/本地/缺失数、整体规模、模块4 各策略数与新周、下载历史表加一行、未下载项;本地数用 `os.walk` 实测(`点睛焱究所/`),远端数用本次检查结果。

### Python 3.10+ 兼容性

SQLite 导入脚本的最低运行版本为 Python 3.10。类型标注应使用现代内置泛型与联合类型:
- `list[X]`、`dict[K, V]`、`tuple[X, Y]`
- `X | None`，而非 `Optional[X]`

Ruff 通过 `python3 -m ruff check .` 调用。当前启用 `E/F/I/N/W/UP`；`E501`（生成模板长行）和 `E402`（脚本调整项目路径后导入）为项目显式例外。

### Git / 网络注意事项

- 通过端口 7897 的代理(Clash)访问 GitHub: `git -c http.proxy=http://127.0.0.1:7897`
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
- **量化指增周报 V1**: 基准、横截面、管理人排名、Watchlist、异常和数据质量均先进入结构化 facts，再渲染 Markdown
- **V2A 风格环境**: 12 条指数日线、10 个代理、本周/近4周/近12周、类别结论、连续同向、12周切换和热力图
- **V2A 防错**: 缓存原子更新、指数身份校验、最大滞后、中性阈值、完整类别覆盖及未来数据截断
