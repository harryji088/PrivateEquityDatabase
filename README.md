# 量化私募业绩数据库 & 交互看板

量化私募基金周度业绩数据的导入、存储、分析与可视化平台。从“点睛业绩放送”Excel 周报中解析数据，计算累计净值，生成自包含的交互式 HTML 看板，并基于 SQLite、基准和风格指数缓存离线生成量化指增周报。

## 数据概览

| 指标 | 数值 |
|------|------|
| 基金公司 | 145 家 |
| 基金产品 | 396 只 |
| 策略类型 | 7 种 |
| 覆盖周数 | 35 周（2026/01/09 – 2026/09/11）|
| 基准指数 | 6 条（沪深300、中证500、中证800、中证1000、中证2000、A500）|
| V2A 风格指数 | 12 条日线、10 个风格代理 |

### 策略分类

| 策略 | 内部标识 | 对比基准 |
|------|----------|----------|
| 量化选股 | `stock_long` | 中证1000 |
| 市场中性 | `market_neutral` | 基准=0（超额=绝对收益）|
| 500指增 | `index_500` | 中证500 |
| 1000指增 | `index_1000` | 中证1000 |
| 300指增 | `index_300` | 沪深300 |
| 2000指增 | `index_2000` | 中证2000 |
| A500指增 | `index_a500` | A500 |

## 项目结构

```
QuantFundDatabase/
├── data/                              # 临时导入工作区（正本见 点睛焱究所/…/量化股票/，用完即清）
│   └── 点睛业绩放送_*.xlsx
├── benchmark_nav.json                 # 基准指数日频净值（CSIndex 官网 API）
├── style_index_nav.json               # V2A 风格指数日频净值（本地缓存，不入库）
├── backend/
│   ├── analytics/                     # 只读周报事实计算层
│   └── scripts/
│       ├── import_weekly_sqlite.py     # 数据导入：Excel → SQLite
│       ├── update_benchmark.py        # 基准更新：CSIndex API → benchmark_nav.json
│       ├── update_style_indices.py    # V2A 风格更新：CSIndex API → style_index_nav.json
│       └── rebuild_dashboard.py       # 看板生成：SQLite → dashboard.html
├── config/                            # 周报策略与 Watchlist 配置
├── reports/weekly/                    # 已生成的 Markdown 周报
├── dashboard.html                      # 生成产物：自包含交互看板（本地，不入库）
├── index.html                          # = dashboard.html 的本地副本（本地打开用，不入库）
├── docs/index.html                     # = dashboard.html，GitHub Pages 部署用（入库）
├── cc_data.sqlite3                     # SQLite 数据库（本地，不入库）
└── merged_weekly_returns.csv           # 合并周收益 CSV 导出（本地，不入库）
```

## 数据管道

### 1. 导入周度数据

```bash
cd backend && python3 scripts/import_weekly_sqlite.py
```

解析 `data/` 下的 Excel 周报（正本在 `点睛焱究所/4. 周度业绩排名更新及业绩点评/周度业绩/2026/量化股票/`，当前覆盖 0105–0911；导入前需复制进 `data/`），每个文件含 7 个策略 sheet，列布局因周次略有差异（14–17 列）。脚本自动识别列名，统一入库到 SQLite。

**入库字段：**

| 字段 | 来源 | 说明 |
|------|------|------|
| `weekly_return` | Excel「近一周收益」| 周度收益率 |
| `weekly_excess` | Excel / **脚本计算** | 周度超额收益（量化选股用中证1000计算）|
| `ytd_return` | Excel「今年以来收益率」| 年内累计收益（小数）|
| `ytd_excess` | Excel / **脚本计算** | 年内累计超额（量化选股用中证1000计算）|
| `ytd_drawdown` | Excel「今年以来动态回撤」| 净值从峰值回撤幅度 |
| `ytd_excess_drawdown` | **脚本统一计算** | 超额从峰值回撤（基于 ytd_excess 计算，不读 Excel）|
| `ann_return` | Excel「今年以来年化收益率」| 年化收益 |
| `ann_vol` | Excel「年化波动率」| 年化波动率 |
| `max_drawdown` | Excel「最大回撤」| 历史最大回撤 |
| `sharpe` | Excel「Sharpe」| 夏普比率 |
| `rank` | Excel「排名」| 当周策略内排名 |
| `size_category` | Excel「规模」| 管理规模分类 |

**导入后处理管线：**

```
Excel 原始数据
  ↓
1. 市场中性填充: weekly_excess = weekly_return, ytd_excess = ytd_return
    （基准=0，超额=绝对收益）
  ↓
2. 量化选股超额: 以中证1000为基准计算 weekly_excess 和 ytd_excess
    weekly_excess = (1 + fund_return) / (1 + benchmark_return) − 1
    ytd_excess    = (1 + fund_ytd_return) / (1 + benchmark_ytd_return) − 1
  ↓
3. 全策略超额回撤: 从 ytd_excess 统一计算 ytd_excess_drawdown
    excess_nav  = 1.0 + ytd_excess
    peak        = max(excess_nav[0..i])
    drawdown    = (excess_nav − peak) / peak   （≤0，0=在峰值）
```

- **规模分类标准化**：`~` → `-`（如 `50~100亿`）
- **累计净值**：`nav = 1.0 + ytd_return`（年初 = 1.0），缺失周保持空值不填充

### 2. 更新基准指数数据

```bash
cd backend && python3 scripts/update_benchmark.py
```

从 **CSIndex 官网 API** (`csindex.com.cn`) 拉取 6 个基准指数的日频收盘价，增量追加到 `benchmark_nav.json`。AKShare 不再使用（中证2000 的 Sina API 已不可用）。

### 3. 生成看板

```bash
cd backend && python3 scripts/rebuild_dashboard.py
```

从 SQLite 读取全量数据，构建三个数据对象嵌入 HTML 模板：

| 数据对象 | 内容 | 用途 |
|----------|------|------|
| `ABS_DATA` | `nav = 1 + ytd_return`, `excess = ytd_excess` | 绝对收益 Tab |
| `EXCESS_DATA` | `nav = 1 + ytd_excess`, `excess = ytd_excess` | 超额收益 Tab |
| `EXCESS_DD_DATA` | `nav = 1 + ytd_excess_drawdown`, `excess = ytd_excess_drawdown` | 超额回撤 Tab |

每个对象包含：基金列表（含 NAV 序列和超额序列）、策略均值、周度排名数据、基准指数日频数据。

看板文件自包含（~3.7MB），无需服务器，浏览器直接打开即可。

### 4. 更新 V2A 风格指数缓存

```bash
make update-style
```

从中证指数官网拉取并增量缓存 12 条价格指数日线：大小盘、300/500/1000 成长价值、300 动量、300/500/1000 行业中性低波动和中证红利。标的代码和口径见 [V2 风格数据标的清单](docs/V2_STYLE_DATA_INSTRUMENT_LIST.md)。

`style_index_nav.json` 仅保存在本地；周报生成时只读该缓存，不联网。缓存路径由 `config/weekly_report.yaml` 的 `style.data_path` 控制。

更新器采用“先全部更新并验收、再原子替换”的方式：默认任一指数失败都不覆盖正式缓存；同时校验指数名称、Wind 代码、CSIndex 代码、日期顺序、重复日期及最新日期。`--allow-partial` 只允许为失败指数保留完整、身份正确且仍在新鲜度范围内的旧缓存。

### 5. 生成量化指增周报

```bash
make weekly-report-validate  # 只读校验，不生成文件
make weekly-report           # 生成 facts JSON 和 Markdown 周报
```

周报只读取项目根目录的 `cc_data.sqlite3`、`benchmark_nav.json`、`config/` 下的 YAML，以及 `style.data_path` 指向的本地风格缓存；不会更新数据库、调用网络或改变 Dashboard。V1 范围为 300/500/1000/2000/A500 指增，数据实体为“管理人 × 策略”，周超额直接复用数据库的正式 `weekly_excess` 字段。V2A 新增指数风格收益差、类别风格结论、连续同向周数、12 周切换次数和方向热力图；类别内全部配置代理均有数据且同向才给出占优/不占优，短线反转不等同趋势确认。默认将绝对收益差不超过 0.05% 视为中性，并拒绝使用滞后超过 4 个自然日或窗口内没有新增观测的指数数据。不包含全A宽度、成交、个股因子或真实归因。

生成物为 `data/derived/weekly/{日期}/report_facts.json`、校验结果和 `reports/weekly/{日期}.md`。为保护历史文件，若同一日期已存在，默认失败；确认需要重生成时直接执行：

```bash
cd backend && python3 scripts/generate_weekly_report.py --overwrite
```

重点管理人由 `config/focus_managers.yaml` 管理；初始名单为衍复、孝庸、平方和、顽岩和华年。配置中的短名只作别名，报告始终使用数据库标准名称。
V1 报告时区固定为 `Asia/Shanghai`，`recent_windows` 必须包含 4 周和 12 周，与固定 Markdown 栏目保持一致。

周报事实层与展示层分离：所有指标、日期、阈值和风格结论先写入 `report_facts.json`，Markdown 只负责渲染。风格收益差采用“多头腿窗口累计收益 − 对照腿窗口累计收益”，不是单周差值累加，也不是产品几何超额。

### 6. 一键更新与质量检查

```bash
make update-all                         # 看板数据 → V2A 风格缓存 → 周报
make test                               # 当前 32 项后端测试
cd backend && python3 -m ruff check .  # Ruff 静态检查
```

项目最低支持 Python 3.10；当前本机验证环境为 Python 3.13。Ruff 的 `E501`（生成模板长行）和 `E402`（脚本调整项目路径后导入）为显式例外，其余启用 `E/F/I/N/W/UP` 规则。

## 看板功能

右上角 **3 个 Tab** 切换视图，所有 Tab 共享同一套 8 板块布局，板块标题和图表数据随 Tab 动态切换：

| # | 板块 | 绝对收益 | 超额收益 | 超额回撤 |
|---|------|----------|----------|----------|
| ① | 策略走势 | 7 策略平均净值 + 6 基准 | 6 策略平均超额曲线 | 6 策略平均超额回撤曲线 |
| ② | 产品对比 | 按策略/规模筛选 + 基准叠加 | 超额净值对比 | 超额回撤对比 |
| ③ | 周度排名 | 周度收益排名 + 柱状图 | 周度超额排名 | — |
| ④ | YTD 排名 | 累计净值与 YTD 收益排名 | 今年以来超额排名 | 最大超额回撤排名 |
| ⑤ | 单基金对比 | 多选基金叠加基准 | 多选基金超额叠图 | 多选基金回撤叠图 |
| ⑥ | 净值排名矩阵 | 全量基金 × 周累计净值（左 7 列冻结）| 超额净值矩阵 | 超额回撤矩阵 |
| ⑦ | 收益排名矩阵 | 各周净值名次（绿前红后，左 6 列冻结）| 各周超额名次 | 各周回撤名次 |
| ⑧ | 周超额矩阵 | — | 各周单周超额，按周胜率排序（左 7 列冻结）| — |

### 产品详情弹窗（点击基金名）

单击任意基金名即可弹出详情窗口，包含：

- **8 个指标卡**：区间累计收益、年化收益、累计超额、年化波动率、最大回撤、Sharpe、周胜率、数据周数
- **时间范围选择器**：可自定义起止周，指标和图表联动更新
- **左图 — 累计净值 + 超额收益**（双 Y 轴线图）
  - 金色实线：`nav = 1.0 + ytd_return`（左轴，净值）
  - 蓝色虚线：`ytd_excess`（右轴，%）
  - Tooltip：净值显示 4 位小数，超额显示百分比
- **右图 — 超额回撤曲线**（红色渐变面积图）
  - 算法：`drawdown = ytd_excess - running_peak(ytd_excess)`，Y 轴 `max=0`
  - 0 线在顶部，曲线向下=回撤加深，红色区域越深=回撤越大
- **独立于 Tab**：始终使用绝对收益数据（`ABS_DATA`），三个 Tab 打开同一产品内容一致
- 支持窗口 resize、暗色/亮色主题

### 交互特性

- **三维筛选**：策略类型 × 规模分类 × 管理人搜索，选策略后规模下拉按该策略可见规模刷新且不覆盖已选规模
- **产品点击**：表格和矩阵中的基金名可点击，弹出产品详情窗口
- **暗色/亮色双主题**：右上角按钮一键切换，偏好自动保存到 localStorage
- **ECharts 图表**：自适应窗口，tooltip 联动，图例切换，百分比格式化
- **矩阵冻结列**：⑥⑦⑧ 矩阵冻结日期列左侧的全部标签列（⑥/⑧ 冻 7 列，⑦ 冻 6 列），横向滚动时始终可见
- **中国涨跌色**：红涨绿跌（红 `#e74c3c` / 绿 `#27ae60`），全程一致
- **公司名合并**：导入时统一混用名（如 衍盛私募 → 衍盛资产），避免同一家公司拆成两家

## 技术栈

| 层 | 技术 |
|----|------|
| 数据导入 | Python 3.10+, openpyxl, sqlite3 |
| 基准数据 | CSIndex 官网 API (`csindex.com.cn`) |
| 看板生成 | Python f-string 模板，内嵌 JS/CSS |
| 图表 | ECharts 5 (CDN)，含 LinearGradient 面积图 |
| 样式 | CSS 自定义属性，暗色/亮色双主题 |
| 数据存储 | SQLite（cc_data.sqlite3），JSON（benchmark_nav.json、style_index_nav.json）|
| 部署形态 | 单文件 HTML（~3.7MB），零依赖浏览器打开 |

## 维护说明

- 基准和 V2A 风格数据通过 CSIndex 官网 API 自动拉取更新（AKShare 已弃用，中证2000 的 Sina 源不可用）
- `make update-data` 一键完成「更新基准 → 导入周度 → 生成看板」全流程（顺序固定，因导入时计算超额需读取最新基准）
- `make update-all` 在上述流程后再更新风格缓存并生成周报；`make weekly-report` 前应先执行一次 `make update-style`
- 周报默认不覆盖同日期历史产物；确认重生成时使用 `cd backend && python3 scripts/generate_weekly_report.py --overwrite`
- `docs/index.html` 是 GitHub Pages 部署源；`dashboard.html` / `index.html` 为本地生成产物，不入库

---

*数据来源：点睛业绩放送 周度 Excel 报告（当前入库覆盖 2026/01 – 2026/09）*
