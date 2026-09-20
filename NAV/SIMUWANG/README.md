# 私募排排网历史净值批量采集

从已获授权访问的私募排排网产品页批量读取“历史净值/分红”数据。脚本使用独立浏览器会话，不要求把用户名、密码、Cookie 或网站 Token 写入代码。

## 解码原理

网站把单位净值和累计净值渲染成 Base64 PNG 字形，并混入隐藏图片。脚本会：

1. 打开“历史净值/分红”页签并触发每批 10 条的懒加载。
2. 只保留实际位于净值单元格内的可见图片。
3. 从图片中分割数字字形，过滤透明和白色干扰。
4. 用页面的成立以来收益和逐期净值变动自动校准 `图片字形 → 数字`。
5. 重新计算相邻两期收益率，校验解码结果后才写入文件。

脚本不执行网站返回的动态 JavaScript 解码代码，也不读取或导出浏览器 Cookie。

## 文件说明

- `scrape_nav.py`：批量浏览器采集和断点续跑。
- `nav_decoder.py`：PNG 数字分割、识别和净值校验。
- `products.example.csv`：产品清单模板。
- `products.csv`：本地实际清单，不提交 Git。
- `../output/备案编号-产品名-起始日期-结束日期.csv`：每个产品独立的历史净值文件。
- `state/progress.json`：断点续跑状态和失败原因。
- `~/.config/simuwang-browser-profile/`：登录会话，默认放在项目外以避免 iCloud 同步。

## 安装

```bash
cd NAV/SIMUWANG
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
cp products.example.csv products.csv
```

## 产品清单

```csv
product_name,product_url,latest_cumulative_nav
顽岩量化选股1号,https://dc.simuwang.com/product/HF0000CB02.html?chat_off=0,
```

`latest_cumulative_nav` 通常留空，脚本会根据“成立以来收益”推导。如果某个页面没有显示成立以来收益，或推导值与页面最新累计净值不同，可在该列手工填写最新的“分红再投资累计净值”。

也接受中文表头：`产品名称,产品地址,最新累计净值`。

## 运行

```bash
python3 scrape_nav.py
```

首次运行会打开浏览器。请自行完成登录、验证码以及网站要求的风险提示确认；脚本不会代为处理这些步骤。

输出字段：

```text
product_name, product_url, fund_id, date, unit_nav,
product_code, cumulative_nav_reinvest, cumulative_nav_no_reinvest,
change_pct, scraped_at
```

默认跳过已经完成的产品。重新抓取并合并最新数据：

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

建立登录会话后可尝试：

```bash
python3 scrape_nav.py --headless --refresh
```

## 注意事项

- 仅采集账号有权访问的数据，并遵守网站使用约定。
- 登录会话目录包含敏感信息，请勿分享或同步。
- 页面结构、图片字体或净值口径变化时，脚本会因校验不通过而停止该产品，避免静默写入错误值。
- 本地运行不调用 OpenAI API，不消耗模型 Token。
