# PrivateEquityDatabase：量化指增周度分析与周报实施方案

> 文档类型：Implementation Plan / SPEC  
> 面向执行者：Codex 及后续维护 Agent  
> 目标仓库：`harryji088/PrivateEquityDatabase`  
> 首期范围：只使用现有 SQLite 数据库与 `benchmark_nav.json`，不新增外部行情或研究数据源

## 1. 目标与非目标

### 1.1 目标

在现有“更新数据 → 重建看板”的流程后增加一条稳定、可复核的周度分析链路：

```text
现有周度数据 + benchmark_nav.json
              ↓
        analytics 指标层
              ↓
      report_facts.json 事实层
              ↓
     weekly_report.md 周报生成层
```

最终每周执行一次命令即可完成：

1. 读取 SQLite 与基准数据。
2. 计算指数、产品、管理人横截面和重点管理人指标。
3. 生成机器可读的 `report_facts.json`。
4. 根据事实生成 Markdown 周报。
5. 保留历史周报，便于复盘与回溯。

周报要回答四个问题：

> 本周市场是什么环境？量化指增整体表现如何？管理人之间是否出现明显分化？重点关注的管理人是否发生了值得跟踪的变化？

### 1.2 非目标

V1 不做以下事项：

- 不接入新的行情 API、Wind、聚源、券商研报或网页抓取。
- 不在数据库中重构真实基金产品主数据；继续沿用现有“管理人 × 策略”统计口径。
- 不在 V1 实现完整 Barra 因子、行业归因、成交额、换手率、融资融券或基差分析。
- 不让 LLM 直接读取数据库或自己计算收益、排名、分位数、回撤。
- 不改造现有 Dashboard 的业务逻辑；analytics 应作为可复用的旁路能力。
- 不把周报生成做成必须运行的在线服务。

## 2. 设计原则

### 2.1 Python 负责事实，生成器负责表达

所有可验证的数值必须由 Python 计算并写入事实层：

- 收益、超额收益、累计收益。
- 中位数、P25、P75、均值、标准差。
- 正超额比例、管理人数量、样本覆盖率。
- 同类排名、同类百分位、排名变化。
- 滚动窗口、连续正负超额、超额回撤。
- 异常标签及触发原因。

Markdown 生成器只能把已计算事实渲染成报告。若未来接入 LLM，LLM 只能接收 `report_facts.json`，负责把事实转成投研语言，不得重新计算或补造数字。

### 2.2 指标必须可追溯

每一个报告数字都应能追溯到：

- 统计截止日 `as_of_date`。
- 数据源名称和数据表。
- 策略口径。
- 样本数 `sample_size`。
- 缺失值处理方式。
- 指标定义版本 `schema_version` / `analytics_version`。

### 2.3 中位数优先，均值作为补充

私募横截面容易受极端值影响。报告正文默认使用中位数；均值、最大值、最小值和尾部数据放入附表或事实层。

### 2.4 先做稳定的 V1，再逐步增加环境解释

V1 先把“结果”和“异常”跑通；V2 再加入市场环境数据；V3 再接入风格、归因和 LLM 辅助叙事。不要为了等待完整市场数据而阻塞第一版周报。

## 3. 现有项目假设与实现前核对

Codex 开始编码前，必须先检查仓库实际结构，不要假设以下文件名一定完全一致：

```text
backend/scripts/import_weekly_sqlite.py
backend/scripts/update_benchmark.py
backend/scripts/rebuild_dashboard.py
benchmark_nav.json
Makefile
```

实现前执行以下只读检查：

1. 找到 SQLite 路径、建表脚本和现有查询函数。
2. 找到周度收益字段、基准字段、管理人字段、策略字段、日期字段。
3. 找到 `benchmark_nav.json` 的实际结构及日期格式。
4. 找到现有 Makefile 目标的真实名称和依赖关系。
5. 查阅 `AGENTS.md`、README 及现有测试约定。
6. 若字段名不同，优先在适配层映射，不要大范围改动既有导入和看板逻辑。

若 SQLite 中某个指标已经存在，直接复用并通过测试验证；不要在 analytics 层重复定义出另一套口径。

## 4. 推荐目录结构

在不破坏现有目录的前提下新增以下结构。若仓库已有同名模块，应扩展而不是重复创建。

```text
analytics/
├── __init__.py
├── data_access.py             # SQLite 与 benchmark_nav.json 的只读适配
├── metrics.py                 # 通用统计、收益、分位数、回撤函数
├── benchmark_analysis.py      # 基准表现、基准收益序列
├── universe_analysis.py       # 管理人×策略横截面
├── manager_analysis.py        # 单管理人及重点管理人分析
├── anomaly_detection.py       # 正负异常规则
├── facts_builder.py           # 组织并校验 report_facts.json
└── schemas.py                 # dataclass / TypedDict / JSON schema

config/
├── focus_managers.yaml        # 重点关注管理人配置
└── weekly_report.yaml         # 报告窗口、策略映射、阈值和显示配置

scripts/
└── generate_weekly_report.py  # CLI 入口：读取数据、计算 facts、渲染报告

reports/
└── weekly/
    ├── 2026-09-11.md
    ├── 2026-09-18.md
    └── latest.md              # 可选：复制或生成指向最新报告的文件

data/derived/
└── weekly/
    └── 2026-09-18/
        ├── report_facts.json
        └── report_validation.json

tests/
├── analytics/
│   ├── test_metrics.py
│   ├── test_universe_analysis.py
│   ├── test_manager_analysis.py
│   ├── test_anomaly_detection.py
│   └── test_facts_schema.py
└── fixtures/
    ├── weekly_sample.sqlite
    └── benchmark_nav_sample.json
```

`data/derived`、`reports` 的实际路径应服从仓库现有约定。不要为了新功能复制一份 SQLite 或另建第二套 benchmark 文件。

## 5. 配置设计

### 5.1 `config/focus_managers.yaml`

配置只表达“关注谁”和“按什么策略关注”，不保存动态指标。

```yaml
version: 1

focus_managers:
  - name: 示例管理人A
    aliases: [示例管理人A有限公司]
    strategies: [index_1000]
    priority: high
    enabled: true
    note: 重点跟踪

  - name: 示例管理人B
    aliases: []
    strategies: [index_500, index_1000]
    priority: medium
    enabled: true
    note: 观察风格稳定性
```

约定：

- `name` 必填，优先匹配数据库标准名称。
- `aliases` 用于兼容历史名称，不参与展示名称。
- `strategies` 为空表示跟踪该管理人的所有支持策略。
- `priority` 只影响排序和展示，不参与评分。
- 配置中找不到对应管理人时，报告应产生 warning，不应静默忽略。

### 5.2 `config/weekly_report.yaml`

```yaml
version: 1
report:
  output_dir: reports/weekly
  facts_dir: data/derived/weekly
  lookback_weeks: 12
  recent_windows: [1, 4, 12]
  min_sample_size: 5
  timezone: Asia/Shanghai

strategies:
  index_300:
    label: 300指增
    benchmark_key: CSI300
  index_500:
    label: 500指增
    benchmark_key: CSI500
  index_1000:
    label: 1000指增
    benchmark_key: CSI1000
  index_2000:
    label: 2000指增
    benchmark_key: CSI2000
  index_a500:
    label: A500指增
    benchmark_key: A500

anomalies:
  negative_weekly_percentile: 0.10
  positive_weekly_percentile: 0.90
  negative_rank_change_percentile_points: 25
  consecutive_negative_weeks: 3
  consecutive_positive_weeks: 3
  weekly_excess_sigma: 2.0
  min_history_weeks_for_drawdown: 8

display:
  percent_digits: 2
  max_focus_managers: 12
  max_alerts: 10
```

所有阈值进入配置，不要散落在 Python 代码中。配置读取错误、策略映射缺失或阈值不是数值时，应立即失败并给出清晰错误。

## 6. V1 数据模型与事实层

### 6.1 V1 输入数据

V1 只允许读取：

1. 现有 SQLite 数据库。
2. 现有 `benchmark_nav.json`。
3. `focus_managers.yaml` 与 `weekly_report.yaml`。

不允许在 V1 中为了补充指标而引入网络请求、手工粘贴的新数据文件或隐式环境变量。

### 6.2 内部标准记录

在 `data_access.py` 中将数据库字段映射为稳定的内部结构，建议至少包含：

```python
WeeklyObservation(
    as_of_date: date,
    manager_name: str,
    strategy_key: str,
    strategy_label: str,
    product_return: float | None,
    benchmark_return: float | None,
    excess_return: float | None,
    source_row_id: str | None,
)
```

若现有数据只有产品周收益而没有独立的基准周收益，则由 `benchmark_nav.json` 计算基准收益；若现有数据库已有同口径超额字段，应在适配层明确选择数据库字段或重算字段，并在 facts 的 `methodology` 中记录。

### 6.3 `report_facts.json` 顶层结构

```json
{
  "schema_version": "1.0",
  "analytics_version": "v1",
  "generated_at": "2026-09-19T10:00:00+08:00",
  "as_of_date": "2026-09-18",
  "previous_as_of_date": "2026-09-11",
  "data_sources": {
    "database": "path/to/database.sqlite",
    "benchmark_nav": "path/to/benchmark_nav.json"
  },
  "methodology": {
    "return_unit": "decimal",
    "excess_definition": "product_return - benchmark_return",
    "quantile_method": "linear",
    "min_sample_size": 5
  },
  "data_quality": {
    "status": "ok",
    "warnings": [],
    "missing_strategies": [],
    "sample_coverage": 0.98
  },
  "market": {},
  "strategy_summary": [],
  "strategy_trend": [],
  "focus_managers": [],
  "alerts": []
}
```

金额、收益、比例统一以小数存储，例如 `0.0123` 表示 `1.23%`。只有 Markdown 渲染层负责格式化百分号和小数位。

### 6.4 策略汇总对象

```json
{
  "strategy_key": "index_1000",
  "strategy_label": "1000指增",
  "benchmark_key": "CSI1000",
  "as_of_date": "2026-09-18",
  "sample_size": 86,
  "benchmark_return": 0.0215,
  "product_return": {
    "mean": 0.0261,
    "p25": 0.0220,
    "median": 0.0260,
    "p75": 0.0304,
    "min": 0.0101,
    "max": 0.0412,
    "std": 0.0068
  },
  "excess_return": {
    "mean": 0.0046,
    "p25": 0.0010,
    "median": 0.0042,
    "p75": 0.0078,
    "min": -0.0080,
    "max": 0.0190,
    "std": 0.0051,
    "dispersion_p75_p25": 0.0068
  },
  "positive_excess_ratio": 0.67,
  "ranked_managers": [],
  "rolling": {
    "weeks_4": {
      "median_excess": 0.0120,
      "positive_ratio": 0.61
    },
    "weeks_12": {
      "median_excess": 0.0310,
      "positive_ratio": 0.58
    }
  },
  "comparison": {
    "median_excess_change": 0.0015,
    "dispersion_change": 0.0021,
    "positive_ratio_change": -0.04
  }
}
```

## 7. 指标定义

### 7.1 基准收益

对基准净值序列按周末或报告截止日计算：

```text
benchmark_return(t) = NAV(t) / NAV(previous_observation) - 1
```

若报告日不在基准序列中，取不晚于报告日的最近可用观测，并在数据质量中记录实际使用日期。

### 7.2 产品收益与超额

若产品周收益为简单收益：

```text
excess_return = product_return - benchmark_return
```

V1 使用简单超额，不混用几何超额。若仓库已有正式超额字段，必须保留其现有口径并在 `methodology.excess_definition` 明示。

### 7.3 横截面统计

对每个报告日、每个策略，在剔除缺失值后计算：

- `sample_size`
- 均值 `mean`
- P25、P50/中位数、P75
- 最小值、最大值、标准差
- `dispersion_p75_p25 = P75 - P25`
- `positive_excess_ratio = count(excess_return > 0) / sample_size`

样本数小于 `min_sample_size` 时，该策略可以展示，但标记为 `insufficient_sample`，不触发强结论或排名异常。

### 7.4 排名与同类百分位

默认按周超额从高到低排名，排名从 1 开始；并列时使用稳定排序：

1. 超额降序。
2. 管理人名称升序。

同类百分位定义为：

```text
percentile = (sample_size - rank) / (sample_size - 1)
```

当样本数为 1 时百分位为 `null`。展示时 `0.85` 表示位于同类前 15%，不是“第 85 名”。

排名变化：

```text
rank_change = previous_rank - current_rank
```

正数表示排名提升，负数表示排名下降。若管理人或策略在前一周不存在，使用 `null`，不要当作从 0 名开始变化。

### 7.5 滚动指标

对每个管理人×策略，至少计算：

- 近 4 周累计产品收益。
- 近 4 周累计超额：每周超额简单累加，V1 明确记录口径。
- 近 12 周累计超额。
- 近 4 周正超额周数 / 有效周数。
- 连续正超额周数、连续负超额周数。
- 当前累计超额曲线及从历史高点的超额回撤。

超额回撤定义：

```text
cum_excess(t) = sum(excess_return_1 ... excess_return_t)
drawdown(t) = cum_excess(t) - max(cum_excess(1 ... t))
```

当前超额回撤为最后一个有效周的 `drawdown`，数值通常小于或等于 0。

### 7.6 市场状态（V1 的可实现版本）

V1 的“市场层”只基于现有 benchmark 序列，不虚构成交和股票广度：

- 各支持基准本周收益。
- 各支持基准近 4 周累计收益。
- 各支持基准近 12 周累计收益。
- 大小盘代理收益差，例如 `CSI300 - CSI1000`、`CSI500 - CSI2000`，前提是两者均存在。
- 基准可用性、缺失日期和实际取值日期。

V1 的市场环境标签只允许输出：`大盘相对占优`、`小盘相对占优`、`风格信号不完整`、`无法判断`。不要把基准涨跌直接表述为“成交活跃”“选股宽度好”“Barra 风格强”。这些指标放入 V2。

## 8. 异常规则

异常检测必须输出结构化对象，不能只拼接文本。

### 8.1 负面异常

对管理人×策略触发以下任一规则：

| 规则 | 默认阈值 | 说明 |
|---|---:|---|
| 周度后尾 | 周超额 ≤ 同类 P10 | 样本数足够时触发 |
| 单周极端负超额 | ≤ 同类均值 - 2σ | 样本数不足时不触发 |
| 连续负超额 | ≥ 3 周 | 连续窗口内均为有效数据 |
| 近 4 周尾部 | 4 周累计超额 ≤ 同类 P10 | 以管理人横截面排名为准 |
| 排名显著下降 | 百分位下降 ≥ 25 个百分点 | 必须有上周可比记录 |
| 超额回撤 | 当前回撤进入自身历史最差 10% | 历史至少 8 周 |

### 8.2 正面异常

| 规则 | 默认阈值 | 说明 |
|---|---:|---|
| 周度前列 | 周超额 ≥ 同类 P90 | 样本数足够时触发 |
| 连续正超额 | ≥ 3 周 | 连续窗口内均为有效数据 |
| 排名显著提升 | 百分位提升 ≥ 25 个百分点 | 必须有上周可比记录 |
| 近 4 周改善 | 4 周累计超额 ≥ 同类 P90 | 只作为改善信号 |
| 回撤修复 | 从最近回撤低点明显修复 | 需在事实中提供修复幅度 |

### 8.3 异常对象

```json
{
  "severity": "negative",
  "code": "CONSECUTIVE_NEGATIVE_EXCESS",
  "manager_name": "示例管理人A",
  "strategy_key": "index_1000",
  "as_of_date": "2026-09-18",
  "evidence": {
    "consecutive_negative_weeks": 3,
    "weekly_excess": -0.0115,
    "peer_percentile": 0.07,
    "rank_change": -34
  },
  "message_template": "连续三周负超额，且本周位于同类后 10%"
}
```

同一管理人同一周多个规则同时命中时合并展示，但保留所有 `codes` 和证据。报告中按严重性、规则数量、重点关注优先级排序。

## 9. 重点管理人 Watchlist 输出

每个重点管理人至少生成以下事实：

```json
{
  "manager_name": "示例管理人A",
  "strategy_key": "index_1000",
  "priority": "high",
  "current": {
    "product_return": 0.0284,
    "benchmark_return": 0.0215,
    "excess_return": 0.0068,
    "rank": 12,
    "rank_total": 86,
    "peer_percentile": 0.87
  },
  "recent": {
    "weeks_4_cumulative_excess": 0.0142,
    "weeks_4_positive_count": 3,
    "weeks_4_observation_count": 4,
    "ytd_excess": null,
    "current_excess_drawdown": -0.0035
  },
  "comparison": {
    "previous_rank": 31,
    "rank_change": 19,
    "previous_excess": -0.0021
  },
  "alerts": [],
  "data_quality": {"status": "ok", "warnings": []}
}
```

V1 不强行计算 YTD：只有在现有数据有足够年初基准和产品观测时才输出，否则为 `null` 并显示“数据不足”。

## 10. 周报 Markdown 模板

生成器应固定结构，内容来自 facts，不允许依据报告语气临时改变栏目顺序。

```markdown
# 量化私募周度跟踪报告｜{as_of_date}

> 数据截止：{as_of_date}  
> 上期：{previous_as_of_date}  
> 样本覆盖：{coverage}  
> 分析版本：{analytics_version}

## 1. 本周结论

{generated_factual_bullets}

## 2. 市场与基准表现

| 基准 | 本周 | 近4周 | 近12周 |
|---|---:|---:|---:|
| ... | ... | ... | ... |

### 风格代理

| 代理 | 本周差值 | 状态 |
|---|---:|---|
| 沪深300 - 中证1000 | ... | 大盘相对占优 |

> 说明：V1 仅根据现有 benchmark 序列判断，不推断成交、广度或因子环境。

## 3. 指增市场概览

| 策略 | 基准收益 | 产品中位数 | 超额中位数 | P25 | P75 | 分化度 | 正超额比例 | 样本数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

## 4. 近期趋势

| 策略 | 近4周超额中位数 | 近4周正超额比例 | 本周较上周变化 |
|---|---:|---:|---:|
| ... | ... | ... | ... |

## 5. 管理人变化

### 本周表现靠前

| 管理人 | 策略 | 周超额 | 同类百分位 | 排名变化 |
|---|---|---:|---:|---:|
| ... | ... | ... | ... | ... |

### 本周表现靠后

| 管理人 | 策略 | 周超额 | 同类百分位 | 排名变化 |
|---|---|---:|---:|---:|
| ... | ... | ... | ... | ... |

## 6. 重点管理人 Watchlist

### {manager_name}｜{strategy_label}

- 本周：周收益 {product_return}，周超额 {excess_return}，同类 {rank}/{rank_total}，百分位 {peer_percentile}
- 近期：近4周累计超额 {weeks_4_cumulative_excess}，正超额 {positive_count}/{observation_count}
- 变化：排名较上周 {rank_change}，当前超额回撤 {drawdown}
- 状态：{deterministic_status_sentence}

## 7. 本周异常与观察名单

### 负面观察

- **{manager}｜{strategy}**：{evidence_based_reason}

### 状态改善

- **{manager}｜{strategy}**：{evidence_based_reason}

## 8. 数据质量与口径

- 缺失策略：{missing_strategies}
- 样本不足：{insufficient_samples}
- 基准实际取值日期：见 `report_facts.json`
- 超额口径：{excess_definition}
- 其他 warning：{warnings}
```

V1 可以使用确定性模板句生成“状态”段落。例如：

```text
本周超额位于同类前 15%，排名较上周提升 19 名；近 4 周有 3 周取得正超额，暂未触发负面异常。
```

不要在 V1 为了追求文风接入 LLM。先确保报告每次可重复生成、数字可复核。

## 11. 脚本与模块职责

### 11.1 `analytics/data_access.py`

- 打开 SQLite，只读查询。
- 读取 benchmark JSON。
- 统一日期、策略和管理人名称。
- 返回内部标准记录。
- 禁止在此模块计算业务指标。

### 11.2 `analytics/metrics.py`

- `quantiles(values)`。
- `safe_mean(values)`、`safe_std(values)`。
- `positive_ratio(values)`。
- `cumulative_sum(values)`。
- `drawdown_from_series(values)`。
- `rank_desc(values)`、`percentile_from_rank(rank, n)`。
- 所有函数必须定义空值、单值、小样本行为。

### 11.3 `analytics/benchmark_analysis.py`

- 计算本周、近 4 周、近 12 周基准收益。
- 计算可用的大盘/小盘代理差值。
- 输出基准缺失和实际取值日期。

### 11.4 `analytics/universe_analysis.py`

- 按报告日、策略分组。
- 计算产品收益与超额横截面统计。
- 计算管理人排名、同类百分位、排名变化。
- 计算策略滚动指标与分化变化。

### 11.5 `analytics/manager_analysis.py`

- 生成重点管理人卡片。
- 合并本周、近 4 周、近 12 周和历史回撤指标。
- 处理管理人缺失、别名、策略不匹配。

### 11.6 `analytics/anomaly_detection.py`

- 纯函数式实现规则。
- 每条异常输出 code、severity、证据字段和可渲染消息模板。
- 不直接生成 Markdown。

### 11.7 `analytics/facts_builder.py`

- 组装顶层 facts 对象。
- 校验必填字段、数值类型、日期一致性。
- 生成稳定排序的 JSON，保证相同输入产生相同结果。

### 11.8 `scripts/generate_weekly_report.py`

建议 CLI：

```bash
python scripts/generate_weekly_report.py \
  --as-of 2026-09-18 \
  --db path/to/database.sqlite \
  --benchmark benchmark_nav.json \
  --focus-config config/focus_managers.yaml \
  --report-config config/weekly_report.yaml \
  --output-dir reports/weekly \
  --facts-dir data/derived/weekly
```

行为要求：

- 未传 `--as-of` 时使用数据库中最新可用周，但在输出中明确记录。
- 指定日期没有数据时退出非 0，并说明可用的最近日期。
- 默认先生成 facts，再渲染 Markdown。
- facts 校验失败时不生成看似成功的报告。
- 支持 `--validate-only`，只校验数据和事实，不写报告。
- 支持 `--print-summary`，打印简短运行结果。

## 12. Makefile 集成

保留现有目标，新增目标名称以仓库当前风格为准。建议：

```make
.PHONY: analytics weekly-report weekly-report-validate update-all

analytics:
	python scripts/generate_weekly_report.py --validate-only

weekly-report:
	python scripts/generate_weekly_report.py

weekly-report-validate:
	python scripts/generate_weekly_report.py --validate-only

update-all: update-benchmark import-weekly rebuild-dashboard weekly-report
```

如果现有目标名不是 `update-benchmark`、`import-weekly` 或 `rebuild-dashboard`，使用实际目标名，不要为适配此文档重命名旧目标。

建议最终主流程为：

```text
make update-all
  ├─ 更新已有 benchmark
  ├─ 导入已有周度数据
  ├─ 重建已有 dashboard
  └─ 生成 reports/weekly/{as_of_date}.md
```

报告生成失败时 `update-all` 必须失败，避免出现“看板已更新但周报是旧数据”的静默状态。

## 13. 测试要求

### 13.1 单元测试

至少覆盖：

1. 空列表、单值、偶数样本的分位数行为。
2. 缺失值不会进入统计分母。
3. `positive_excess_ratio` 对恰好 0 的处理固定且有测试。
4. 排名并列时结果稳定。
5. 排名变化方向正确。
6. 近 4 周窗口不足时返回 `null` 或明确的有效样本数。
7. 回撤计算在新高、回撤、修复三个阶段正确。
8. P75-P25 分化度正确。
9. 连续正负超额规则正确处理缺失周。
10. P10/P90 异常只在满足最小样本数时触发。
11. Watchlist 别名匹配和未找到管理人的 warning。
12. benchmark 日期不完全匹配时使用最近可用日期并记录。

### 13.2 集成测试

使用最小 fixture SQLite + benchmark JSON，验证：

- CLI 能生成完整 `report_facts.json`。
- CLI 能生成符合模板的 Markdown。
- 相同输入连续运行两次，facts 和报告内容一致（生成时间字段除外）。
- 指定日期没有数据时退出码非 0。
- facts 校验失败时不写入最终报告。
- `make weekly-report-validate` 可以在无网络环境完成。

### 13.3 回归测试

实现完成后必须运行现有项目测试，并至少手工检查：

- 现有 Dashboard 仍可正常生成。
- 现有数据导入不受影响。
- 新增模块不修改生产 SQLite。
- V1 不产生任何网络请求。

## 14. 验收标准

### 功能验收

- [ ] 能从真实 SQLite 与 `benchmark_nav.json` 生成一份指定截止日周报。
- [ ] 报告包含基准表现、策略横截面、管理人排名变化、Watchlist、异常和数据质量。
- [ ] 至少支持当前仓库已有的 300/500/1000/2000/A500 策略或其实际等价映射。
- [ ] `report_facts.json` 可独立被其他渲染器读取。
- [ ] 重点管理人只通过 YAML 配置增删。
- [ ] 所有主要数值可从 facts 直接定位，不依赖模型临场计算。

### 正确性验收

- [ ] 基准收益与现有 benchmark 序列口径一致。
- [ ] 超额定义在 facts 中明确，且和项目现有口径一致。
- [ ] 中位数、P25/P75、正超额比例、分化度、排名变化通过 fixture 手工核对。
- [ ] 异常规则有证据字段，不只输出自然语言。
- [ ] 缺失数据不被静默填 0。
- [ ] 样本不足时不输出强结论。

### 工程验收

- [ ] 不破坏已有看板、导入和基准更新流程。
- [ ] `make weekly-report` 与 `make weekly-report-validate` 可用。
- [ ] 测试在无网络环境通过。
- [ ] 新增代码有模块级说明和 CLI 使用说明。
- [ ] 生成物按日期落盘，不覆盖历史周报。

## 15. 分阶段路线

### V1：可复核的周度指增报告

只依赖 SQLite + `benchmark_nav.json` + YAML 配置。

交付：

- analytics 指标层。
- `report_facts.json`。
- 确定性 Markdown 周报。
- 策略汇总：中位数、P25/P75、正超额比例、分化度。
- 管理人排名、排名变化、同类百分位。
- 近 4 周/12 周趋势。
- Watchlist。
- 正负异常规则。
- Makefile 集成和测试。

V1 的报告价值主线：

```text
基准表现 → 指增横截面 → 管理人变化 → 重点关注 → 数据质量
```

### V2：市场 Alpha 环境解释

在确认数据源和字段后再增加：

- 全 A 上涨比例。
- 各指数成分股胜率。
- 截面收益标准差。
- 成交额、换手率、波动率。
- 大小盘、成长/价值、动量、反转、高低波等风格代理。
- 量化环境标签：选股宽度、截面分化、风格稳定度。
- 12 周热力图和更丰富的图表输出。

V2 必须为每个新增市场指标补充数据来源、日期对齐规则和缺失值规则，不能仅凭报告材料中的概念命名字段。

### V3：研究与智能叙事层

- 真实产品维度与管理人维度分离。
- 管理人风格漂移与基准相关性监控。
- 300/500/1000/2000/小市值相关性及滚动 beta。
- 研究资料与周报事实的关联。
- LLM 仅基于经过 schema 校验的 facts 生成“本周结论”和“重点管理人状态卡”。
- 生成 HTML/PDF、邮件或知识库归档。
- 报告版本比较与历史异常追踪。

## 16. 建议的执行顺序

Codex 按以下顺序实施，不要一开始同时改动导入、看板和报告三条链路：

1. 盘点现有表结构、字段、日期范围、策略映射和 Makefile。
2. 建立只读 `data_access` 适配层和最小 fixture。
3. 实现并测试 `metrics.py`。
4. 实现策略横截面和管理人分析。
5. 实现异常检测。
6. 实现 `report_facts.json` schema 与校验。
7. 用固定模板生成 Markdown。
8. 加入 Watchlist 配置和缺失 warning。
9. 接入 Makefile，先跑 `weekly-report-validate`，再接入 `update-all`。
10. 用真实最新周运行一次，人工核对至少 3 个策略和 3 个重点管理人。
11. 最后再考虑 V2 市场环境数据，避免把 V1 做成不可验证的大项目。

## 17. 交付时 Codex 应报告的内容

实现完成后，Codex 的交付说明至少包含：

- 新增和修改的文件。
- 实际识别到的 SQLite 表、字段和 benchmark 结构。
- 最终采用的超额口径。
- 生成报告的命令和示例路径。
- 测试命令及结果。
- 真实数据运行时的 warning。
- 与本方案不同的地方及原因。
- 尚未实现的 V2/V3 项目。

最终完成标准不是“新增了几个脚本”，而是：在不依赖网络、无需手工计算、数字可回溯的前提下，每周能稳定得到一份回答“市场整体、管理人分化、重点对象和异常变化”的量化指增周报。
