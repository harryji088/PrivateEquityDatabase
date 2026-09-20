# 先修改api_demo文件中的APP_KEY和APP_SECRET

#导入模块
import asyncio
import api_demo

# 设置参数①基金id②净值起始日期③净值结束日期
fund_id='252'
begin_date="2021-01-01"
end_date="2024-02-01"

#调用get_fund_auth_nav函数，并输入参数
rlt=asyncio.run(api_demo.get_fund_auth_nav(fund_id, begin_date, end_date))
print(rlt)

begin_date,end_date=2024,2024
##以下年份格式均可
# begin_date,end_date='2024','2024'
# 输入的历史年份数据应大于等于2015，2015包含2015年以前的数据
rlt=asyncio.run(api_demo.get_fund_auth_nav_batch(begin_date,end_date))
print(rlt.head(3))


begin_date,end_date=202507,202507
#以下两种月份格式均可
# begin_date,end_date='202507','202507'
# begin_date,end_date='2025-07','2025-07'
# 输入的历史月份数据应小于当前月份
rlt=asyncio.run(api_demo.get_fund_auth_nav_batch(begin_date,end_date))
print(rlt.head(3))


begin_date,end_date=20250812,20250812
#以下两种日期格式均可
# begin_date,end_date='20250810','20250810'
# begin_date,end_date='2025-08-10','2025-08-10'
# 输入的日期数据应小于当前日期
rlt=asyncio.run(api_demo.get_fund_auth_nav_batch(begin_date,end_date))
print(rlt.head(3))

#以下两种日期格式均可，不输入日期则自动获取最新批次日期的数据
rlt=asyncio.run(api_demo.get_fund_auth_nav_batch())
print(rlt.head(3))

input('输入任何键结束')