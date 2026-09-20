# 好买私募历史净值批量采集

批量读取账号有权访问的好买私募历史净值页。历史净值地址以 `/lsjz` 结尾，例如：

```text
https://simu.howbuy.com/shanghaikuandesimu/SZP078/lsjz
```

脚本使用独立的持久化浏览器会话，不把用户名、密码或 Cookie 写入代码。首次运行时在打开的浏览器中手工登录，后续复用登录状态。

## 安装

```bash
cd NAV/HOWBUY
python3 -m pip install -r requirements.txt
```

脚本默认使用电脑上已经安装的 Google Chrome，不需要另外下载 Playwright Chromium。

## 产品清单

编辑本地 `products.csv`，每行一个产品：

```csv
product_name,product_url
宽德中证1000指增8号臻享一期,https://simu.howbuy.com/shanghaikuandesimu/SZP078/lsjz
```

也可以填写产品详情页，脚本会自动添加 `/lsjz`：

```text
https://simu.howbuy.com/shanghaikuandesimu/SZP078/
```

支持中文表头 `产品名称,产品地址`。

## 运行

```bash
python3 scrape_nav.py
```

首次运行如果显示需要登录：

1. 在打开的浏览器中完成好买登录和合格投资者确认。
2. 回到终端按回车。
3. 脚本直接访问各产品的 `/lsjz` 页面并自动翻页。

默认跳过已成功产品。重新抓取并合并最新数据：

```bash
python3 scrape_nav.py --refresh
```

每个产品单独生成一个 CSV，文件名格式为 `产品代码-产品名-起始日期-结束日期.csv`，日期使用 `YYYYMMDD`：

```text
../output/SZP078-宽德中证1000指增8号臻享一期-20230414-20260821.csv
```

输出字段包括产品名称、产品代码、净值日期、单位净值、累计净值、涨跌幅和抓取时间。断点状态保存在 `state/progress.json`。

常用参数：

```bash
python3 scrape_nav.py --refresh --delay 3 --retries 2
```

指定输出目录：

```bash
python3 scrape_nav.py --output-dir ../output --refresh
```

登录状态稳定后可尝试无界面运行：

```bash
python3 scrape_nav.py --headless --refresh
```

仅采集账号有权访问的数据，并遵守好买网站的使用约定。页面结构发生变化或出现“登录可见”时，脚本会停止该产品，避免静默写入错误数据。
