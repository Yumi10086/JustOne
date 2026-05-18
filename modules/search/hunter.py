"""
鹰图 (Hunter) API 搜索模块

接口文档: https://hunter.qianxin.com/home/helpCenter?type=api
"""

import base64
import time
from typing import Optional, Set

from common.search import Search
from config import settings
from config.logging import logger


class Hunter(Search):
    """
    鹰图 API 子域收集模块

    使用 /openApi/search 接口进行语法检索。
    search 参数需经 RFC 4648 base64url 编码。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Hunter'
        self.source = 'hunter.qianxin.com'
        self.addr = 'https://hunter.qianxin.com/openApi/search'
        self.delay = 1
        self.key = settings.hunter_api_key

    def _handle_api_error(self, resp) -> bool:
        """
        处理 Hunter API 错误（含 HTTP 200 但 code != 200 的情况）

        :param resp: 响应对象
        :return: True 应该终止，False 可继续
        """
        if resp is None:
            return True
        if resp.status_code != 200:
            code_msg = {
                401: '未授权，API Key 无效或已过期',
                403: '禁止访问，权限不足',
                500: '服务器内部错误',
            }
            msg = code_msg.get(resp.status_code, f'未知错误 (状态码: {resp.status_code})')
            logger.error(f'{self.source} {msg}')
            return True
        try:
            data = resp.json()
            api_code = data.get('code')
            if api_code is not None and api_code != 200:
                err_msg = data.get('message', '未知错误')
                logger.error(f'{self.source} API 错误 (code={api_code}): {err_msg}')
                return True
            return False
        except Exception:
            return False

    def search(self):
        """发送搜索请求并提取子域名"""
        self.page_num = 1
        search_query = f'domain.suffix="{self.domain}"'
        encoded = base64.urlsafe_b64encode(search_query.encode('utf-8')).decode('ascii')
        while True:
            time.sleep(self.delay)
            self.get_header()
            self.proxy = self.get_proxy(self.source)
            self.header['Accept'] = 'application/json'
            query = {'api-key': self.key,
                     'search': encoded,
                     'page': self.page_num,
                     'page_size': 100,
                     'is_web': 3}
            resp = self.get(self.addr, query)
            if not resp:
                return
            if resp.status_code == 429:
                logger.warning(f'{self.source} 请求频率过高 (429)，10 秒后重试')
                time.sleep(10)
                continue
            if self._handle_api_error(resp):
                break
            data = resp.json()
            records = data.get('data', {}).get('arr', [])
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
                        subdomain = record.get('domain') or record.get('url')
                        if subdomain and self.domain in subdomain:
                            self.subdomains.add(subdomain.lower())
            total = data.get('data', {}).get('total') or 0
            if self.page_num * 100 >= int(total):
                break
            if not records or len(records) < 100:
                break
            self.page_num += 1

    def run(self) -> Set[str]:
        """执行鹰图搜索"""
        if not self.have_api(self.key):
            return self.subdomains
        self.begin()
        self.search()
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = Hunter(domain, config)
    return module.run()
