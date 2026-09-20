# FOF99 历史净值批量采集

从已获授权访问的火富牛产品页面批量读取历史净值。脚本使用独立的浏览器登录会话，不要求把用户名、密码或 Cookie 写进代码。

## 文件说明

- `scrape_nav.py`：批量采集脚本。
- `products.example.csv`：产品清单模板。
- `products.csv`：实际产品清单，本地使用且不提交 Git。
- `~/.config/fof99-browser-profile/`：默认登录会话目录，放在项目外，避免随 iCloud 项目同步。
- `../output/产品代码-产品名-起始日期-结束日期.csv`：每个产品独立的历史净值文件；产品代码优先使用页面备案编号。
- `state/progress.json`：断点续跑状态和失败原因。

## 安装

建议在项目已有虚拟环境中执行：

```bash
cd NAV/FOF99
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

## 准备产品清单

```bash
cp products.example.csv products.csv
```

编辑 `products.csv`，每行一个产品：

```csv
product_name,product_url
产品名称,https://mp.fof99.com/fund/view/产品ID
```

也接受中文表头 `产品名称,产品地址`。重复 URL 会自动去重。

## 运行

首次运行：

```bash
python3 scrape_nav.py
```

浏览器打开后，如页面尚未登录，请在浏览器中自行完成登录。登录会话默认保存在项目外的 `~/.config/fof99-browser-profile/`，以后运行通常不必再次登录。

采集成功后会按产品分别生成，例如：

```text
../output/SATW62-产品名称-20230101-20260826.csv
state/progress.json
```

结果字段：

```text
product_name, product_url, date, unit_nav, cumulative_nav,
adjusted_nav, change_pct, scraped_at
```

## 断点续跑与更新

默认跳过 `state/progress.json` 中已经完成的产品，失败产品会在下次运行时重试：

```bash
python3 scrape_nav.py
```

若需要重新抓取所有产品并合并最新净值：

```bash
python3 scrape_nav.py --refresh
```

常用参数：

```bash
python3 scrape_nav.py \
  --products products.csv \
  --output-dir ../output \
  --delay 2 \
  --retries 2
```

已经创建过登录会话后，可尝试无界面模式：

```bash
python3 scrape_nav.py --headless --refresh
```

## 注意事项

- 仅采集账号有权访问的数据，并遵守网站的使用约定。
- `~/.config/fof99-browser-profile/` 包含登录会话，请勿分享或同步；也不要用 `--profile` 把它改到 iCloud 目录。
- 大批量采集时保留适当的 `--delay`，避免给网站造成过高请求压力。
- 网站页面结构变化后，可能需要更新 `SCROLLER_SELECTOR` 或 `ROW_SELECTOR`。
