"""
FOFA API 搜索模块
"""

import base64
import time
from typing import Optional, Set

from common.search import Search
from config import settings
from config.logging import logger


class FoFa(Search):
    """
    FOFA API 子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'FoFa'
        self.source = 'fofa.info'
        self.addr = 'https://fofa.info/api/v1/search/all'
        self.delay = 1
        self.email = settings.fofa_email
        self.key = settings.fofa_api_key

    def _handle_api_error(self, resp) -> bool:
        """
        处理 FOFA API 错误码（含 HTTP 200 + error:true 的情况）

        :param resp: 响应对象
        :return: True 应该终止，False 可继续
        """
        if resp is None:
            return True
        if resp.status_code != 200:
            code_msg = {
                401: '未授权，API Key 无效或已过期',
                403: '禁止访问，权限不足',
                429: '请求频率过高，触发限流',
                500: '服务器内部错误',
            }
            msg = code_msg.get(resp.status_code, f'未知错误')
            logger.error(f'{self.source} {msg} (状态码: {resp.status_code})')
            return True
        try:
            data = resp.json()
            if data.get('error'):
                errmsg = data.get('errmsg', '未知错误')
                logger.error(f'{self.source} API 错误: {errmsg}')
                return True
            return False
        except Exception:
            return False

    def search(self):
        """发送搜索请求并提取 host 字段"""
        self.page_num = 1
        subdomain_encode = f'domain="{self.domain}"'.encode('utf-8')
        query_data = base64.b64encode(subdomain_encode)
        while True:
            time.sleep(self.delay)
            self.get_header()
            self.proxy = self.get_proxy(self.source)
            self.header['Accept'] = 'application/json'
            query = {'email': self.email,
                     'key': self.key,
                     'qbase64': query_data,
                     'fields': 'host',
                     'page': self.page_num,
                     'size': 1000}
            resp = self.get(self.addr, query)
            if not resp:
                return
            data = resp.json()
            if self._handle_api_error(resp):
                break
            results = data.get('results', [])
            for row in results:
                if isinstance(row, list) and len(row) > 0:
                    host = str(row[0]).lower()
                    if self.domain in host:
                        self.subdomains.add(host)
            if len(results) < 1000:
                break
            self.page_num += 1
            if self.page_num > 100:
                logger.debug(f'{self.source} 已达最大页数限制 (100)')
                break

    def run(self) -> Set[str]:
        """执行 FOFA 搜索"""
        if not self.have_api(self.email, self.key):
            return self.subdomains
        self.begin()
        self.search()
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = FoFa(domain, config)
    return module.run()
