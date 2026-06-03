# 量化私募业绩数据库 & 交互看板

量化私募基金周度业绩数据的导入、存储与可视化看板平台。从"点睛业绩放送"Excel 周报中解析数据，计算累计净值，生成自包含的交互式 HTML 看板。

## 数据概览

| 指标 | 数值 |
|------|------|
| 基金公司 | 138 家 |
| 基金产品 | 370 只 |
| 策略类型 | 7 种 |
| 覆盖周数 | 20 周（2026/01/09 – 2026/05/29）|
| 基准指数 | 6 条（沪深300、中证500、中证1000、中证2000、A500、万得全A）|

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
CC/
├── data/                              # 20 个源 Excel 周报
│   └── 点睛业绩放送_*.xlsx
├── benchmark_nav.json                 # 基准指数日频净值（AKShare 拉取）
├── backend/
│   └── scripts/
│       ├── import_weekly_sqlite.py     # 数据导入：Excel → SQLite
│       └── rebuild_dashboard.py       # 看板生成：SQLite → dashboard.html
├── dashboard.html                      # 最终产物：自包含交互看板 (~2.2MB)
├── cc_data.sqlite3                     # SQLite 数据库
├── merged_weekly_returns.csv           # 合并周收益 CSV 导出
├── frontend/                           # React SPA（可扩展框架）
└── docker-compose.yml                  # PostgreSQL + Redis + Backend
```

## 数据管道

### 1. 导入周度数据

```bash
cd backend && python3 scripts/import_weekly_sqlite.py
```

解析 `data/` 下 20 个 Excel 文件，每个文件含 7 个策略 sheet，列布局因周次略有差异（14–17 列）。脚本自动识别列名，统一入库到 SQLite。

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
    weekly_excess = fund_return − benchmark_return
    ytd_excess    = Π(1 + weekly_excess) − 1  （累计复利）
  ↓
3. 全策略超额回撤: 从 ytd_excess 统一计算 ytd_excess_drawdown
    excess_nav  = 1.0 + ytd_excess
    peak        = max(excess_nav[0..i])
    drawdown    = (excess_nav − peak) / peak   （≤0，0=在峰值）
```

- **规模分类标准化**：`~` → `-`（如 `50~100亿`）
- **累计净值**：`nav = 1.0 + ytd_return`（年初 = 1.0），缺失周保持空值不填充

### 2. 生成看板

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

看板文件自包含（~2.2MB），无需服务器，浏览器直接打开即可。

## 看板功能

右上角 **3 个 Tab** 切换视图，所有 Tab 共享同一套 7 板块布局，板块标题和图表数据随 Tab 动态切换：

| # | 板块 | 绝对收益 | 超额收益 | 超额回撤 |
|---|------|----------|----------|----------|
| ① | 策略走势 | 7 策略平均净值 + 6 基准 | 6 策略平均超额曲线 | 6 策略平均超额回撤曲线 |
| ② | 产品对比 | 按策略/规模筛选 + 基准叠加 | 超额净值对比 | 超额回撤对比 |
| ③ | 周度排名 | 周度收益排名 + 柱状图 | 周度超额排名 | — |
| ④ | YTD 排名 | 累计净值与 YTD 收益排名 | 今年以来超额排名 | 最大超额回撤排名 |
| ⑤ | 单基金对比 | 多选基金叠加基准 | 多选基金超额叠图 | 多选基金回撤叠图 |
| ⑥ | 净值矩阵 | 全量基金 × 周累计净值热力图 | 超额净值热力图 | 超额回撤热力图 |
| ⑦ | 排名矩阵 | 策略线内每周名次变化 | 超额排名变化 | 回撤排名变化 |

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

- **三维筛选**：策略类型 × 规模分类 × 管理人搜索（所有筛选器联动）
- **产品点击**：表格和矩阵中的基金名可点击，弹出产品详情窗口
- **暗色/亮色双主题**：右上角按钮一键切换，偏好自动保存到 localStorage
- **ECharts 图表**：自适应窗口，tooltip 联动，图例切换，百分比格式化
- **表格**：固定表头，列排序，行数自适应高度

## 技术栈

| 层 | 技术 |
|----|------|
| 数据导入 | Python 3.9+, openpyxl, sqlite3 |
| 看板生成 | Python f-string 模板，内嵌 JS/CSS |
| 图表 | ECharts 5 (CDN)，含 LinearGradient 面积图 |
| 样式 | CSS 自定义属性，暗色/亮色双主题 |
| 数据存储 | SQLite（cc_data.sqlite3），JSON（benchmark_nav.json）|
| 部署形态 | 单文件 HTML（~2.2MB），零依赖浏览器打开 |

## 未来扩展

- `frontend/` React SPA 对接 PostgreSQL，支持增删改查
- `backend/` FastAPI 已完成 CRUD 脚手架（9 个 domain），待灌入真实数据
- 基准数据可通过 AKShare 自动拉取更新

---

*数据来源：点睛业绩放送 周度 Excel 报告（2026/01 – 2026/05）*
