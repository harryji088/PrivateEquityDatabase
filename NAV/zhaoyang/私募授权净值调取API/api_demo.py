import asyncio
from ggapi import GGApi
from typing import Optional, List, Any  # 添加 typing 模块的导入
import pandas as pd
import numpy as np


###############请修改此处的APP_KEY与APP_SECRET,如果有疑问请联系您的销售#########################
APP_KEY = ''#
APP_SECRET =''#
###############请修改此处的APP_KEY与APP_SECRET,如果有疑问请联系您的销售#########################

def str_to_numbers(target_type: type, s: Optional[str]) -> List[Any]:
    if not s or s.strip() == '':
        return []
    return [target_type(i) for i in s.split(";")]


async def request_fund_auth_nav_data(params: dict) -> dict:
    api = GGApi(
        app_key=APP_KEY,
        secret=APP_SECRET,
        host="https://sntp-api-service.go-goal.cn"
    )
    return await api.async_get(
        api_name="v1/zyfp_dst_fund_auth_nav/list",
        params=params
    )

###################批量获取基金净值的更新净值数据############################
async def request_fund_auth_nav_data_batch(params: dict) -> dict:
    api = GGApi(
        app_key=APP_KEY,
        secret=APP_SECRET,
        host="https://sntp-api-service.go-goal.cn"
    )
    return await api.async_get(
        api_name="v1/zyfp_gen_auth_nav/get_data_url",
        params=params
    )
###################批量获取基金净值的更新净值数据############################

async def get_fund_auth_nav(fund_id,begin_date,end_date) -> None:
    """
    获取基金净值数据并打印结果
    """
    try:
        resp = await request_fund_auth_nav_data({
            "fund_id": fund_id,
            "begin_date": begin_date,
            "end_date": end_date,
        })
        code: int = resp["code"]

        if code == 0:
            data_dict={}
            for i in resp["data"].keys():
                if resp["data"][i]=='':
                   data_dict[i]='' 
                else:
                    data_dict[i]=str_to_numbers(str, resp["data"][i])
            rlt=pd.DataFrame(data_dict)
            rlt['fund_id']=fund_id
            rlt.replace('', np.nan, inplace=True)
            col_list=['fund_id','statistic_date','nav','added_nav','swanav','total_nav','total_asset','share','income_value_per_ten_thousand', 'd7_annualized_return', 'annualized_return', 'pc', 'cpc', 'entry_time', 'update_time',]
            for col_no in col_list[2:-2]:
                rlt[col_no]=rlt[col_no].astype(float)
            return rlt[col_list]
        else:
            print(f'Error: {resp}')
    except KeyError as e:
        print(f"响应数据缺少必要字段: {str(e)}")
    except Exception as e:
        print(f"未知错误: {str(e)}")

###################批量获取基金净值的更新净值数据############################
###########①输入日期处理#############
def process_date(input_date=None):
    """
    处理输入的日期字符串，转换为适合API请求的格式。
    """
    if input_date[0] ==None :
        return {}
    begin_date=str(input_date[0])
    end_date=str(input_date[1])
    if (len(begin_date)==4) and (len(end_date)==4):
        mod1,mod2='start_year','end_year'
    elif (len(begin_date)==6) and (len(end_date)==6):
        mod1,mod2='start_month','end_month'
    elif (len(begin_date)==7) and (len(end_date)==7):
        mod1,mod2='start_month','end_month'
        begin_date=begin_date[:4]+begin_date[5:]
        end_date=end_date[:4]+end_date[5:]
    elif (len(begin_date)==8) and (len(end_date)==8):
        mod1,mod2='start_date','end_date'
        begin_date=begin_date[:4]+"-"+begin_date[4:6]+"-"+begin_date[6:]
        end_date=end_date[:4]+"-"+end_date[4:6]+"-"+end_date[6:]
    elif (len(begin_date)==10) and (len(end_date)==10):
        mod1,mod2='start_date','end_date' 
    else:
        return {'start_date':begin_date,'end_date':end_date}
    #print(f"处理后的开始日期: {begin_date}, 结束日期: {end_date}, 模块1: {mod1}, 模块2: {mod2}")
    return {mod1: begin_date, mod2: end_date}
###################批量获取基金净值的更新净值数据############################
async def get_fund_auth_nav_batch(begin_date=None,end_date=None) -> None:
    """
    获取基金净值批量更新数据并打印结果
    """
    try:
        ##########②根据日期格式选择功能
        input_paras = process_date([begin_date, end_date])
        resp = await request_fund_auth_nav_data_batch(input_paras)
        code: int = resp["code"]
        if code == 0:
            url_list=[]
            ######获取url连接############
            for i in resp["data"]:
                url_list.append(i['file_path'])
            data_list=[]
            ######根据url接接获取数据############
            for url in url_list:
                data_list.append(pd.read_csv(url, encoding='utf-8'))
            #####根据fund_id和statistic_date去重，保留最新的记录############
            rlt=pd.concat(data_list)
            rlt=rlt.sort_values(by=['update_time'], inplace=False).groupby(by=['fund_id','statistic_date']).head(1)
            rlt['is_valid']=rlt['is_valid'].fillna(1)
            return rlt
        else:
            print(f'Error: {resp}')
    except KeyError as e:
        print(f"响应数据缺少必要字段: {str(e)}")
    except Exception as e:
        print(f"未知错误: {str(e)}")
###################批量获取基金净值的更新净值数据############################


if __name__ == '__main__':
    fund_id='252'
    begin_date="2024-01-01"
    end_date="2024-02-01"
    rlt=asyncio.run(get_fund_auth_nav(fund_id=fund_id,begin_date= begin_date,end_date= end_date))
    print("单个产品数据获取：\n",rlt)

    ###################批量获取基金净值的更新净值数据############################
    rlt=asyncio.run(get_fund_auth_nav_batch())
    print("批量数据获取：\n",rlt)
    input('输入任何按键以结束')