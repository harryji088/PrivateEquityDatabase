import httpx
import datetime
import base64
import hmac
import hashlib
from urllib import parse
from typing import Dict, List, Tuple, Any  # 添加 typing 模块的导入

class GGApi(object):
    def __init__(self, app_key: str, secret: str, host: str) -> None:
        self._appKey = app_key
        self._secret = secret
        self._host = host

    async def async_get(self, api_name: str, params: Dict[str, str]) -> Any:  # 使用 typing.Dict
        async with httpx.AsyncClient() as client:
            url = "{}/{}".format(self._host, api_name)
            if params.get('app_key', None) is None:
                params.setdefault('app_key', self._appKey)

            # 直接传递字典给 httpx，无需手动拼接字符串
            signed_params = self._make_param('GET', api_name, params)
            response = await client.get(url, params=signed_params, timeout=3000)

            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"API调用失败: {str(response)}")

    def _make_param(self, method: str, api_name: str, src_params: Dict[str, str]) -> Dict[str, str]:  # 使用 typing.Dict
        # 添加基础参数
        params = {
            "app_key": self._appKey,
            "time_stamp": str(int(datetime.datetime.now().timestamp()))
        }
        params.update(src_params)

        # 过滤空值并排序
        filtered_params = {
            parse.unquote(k): parse.unquote(v) 
            for k, v in params.items() 
            if k != "sign" and v != ""
        }
        sorted_params: List[Tuple[str, str]] = sorted(filtered_params.items(), key=lambda x: x[0])  # 明确类型注解

        # 构建签名原始字符串
        encoded_params = "&".join(
            f"{parse.quote(k, safe='._-')}={self._encode_param_value(v)}" 
            for k, v in sorted_params
        )
        sign_src = f"{method.upper()}&{parse.quote(api_name, safe='._-')}&{parse.quote(encoded_params, safe='._-')}"

        # 生成签名
        sign = base64.b64encode(
            hmac.new(
                self._secret.encode('utf-8'), 
                sign_src.encode('utf-8'), 
                hashlib.sha1
            ).digest()
        ).decode('utf-8').strip()

        # 添加签名并返回最终参数
        signed_params = dict(sorted_params)
        signed_params["sign"] = sign
        return signed_params

    @staticmethod
    def _encode_param_value(value: str) -> str:
        encoded = []
        for char in parse.unquote(value):
            if char.isalnum() or char in ('*', '!', '(', ')'):
                encoded.append(char)
            else:
                encoded.append(f"%{ord(char):02X}")
        return ''.join(encoded)