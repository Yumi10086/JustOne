"""
Google Custom Search API 模块
"""

import random
import time
from typing import Optional, Set

from common.search import Search
from config import settings
from config.logging import logger


class GoogleAPI(Search):
    """
    Google Custom Search API 子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'GoogleAPI'
        self.source = 'google.com'
        self.addr = 'https://www.googleapis.com/customsearch/v1'
        self.key = settings.google_api_key
        self.id = settings.google_api_id
        self.per_page_num = 10

    def _handle_api_error(self, resp) -> bool:
        """处理 Google API 错误"""
        if resp is None:
            return True
        if resp.status_code != 200:
            code_msg = {
                400: '请求参数错误',
                401: '未授权，API Key 无效或已过期',
                403: '禁止访问，每日配额已用尽或项目未启用 Custom Search API',
                429: '请求频率过高，触发限流',
            }
            msg = code_msg.get(resp.status_code, f'未知错误 (状态码: {resp.status_code})')
            try:
                err = resp.json().get('error', {}).get('message', '')
                if err:
                    msg += f': {err}'
            except Exception:
                pass
            logger.error(f'{self.source} {msg}')
            return True
        return False

    def search(self, domain: str, filtered_subdomain: str = ''):
        """
        发送搜索请求并做子域匹配

        :param str domain: 域名
        :param str filtered_subdomain: 过滤的子域
        """
        self.page_num = 1
        while True:
            word = 'site:' + domain + filtered_subdomain
            time.sleep(random.uniform(1, 3))
            self.get_header()
            self.header['Accept'] = 'application/json'
            self.proxy = self.get_proxy(self.source)
            params = {'key': self.key, 'cx': self.id,
                      'q': word, 'fields': 'items/link',
                      'start': self.page_num, 'num': self.per_page_num}
            resp = self.get(self.addr, params)
            if self._handle_api_error(resp):
                break
            subdomains = self.match_subdomains(resp, fuzzy=True)
            if not self.check_subdomains(subdomains):
                break
            self.subdomains.update(subdomains)
            self.page_num += self.per_page_num
            if self.page_num > 100:
                break

    def run(self) -> Set[str]:
        """执行 Google API 搜索"""
        if not self.have_api(self.id, self.key):
            return self.subdomains
        self.begin()
        self.search(self.domain)

        for statement in self.filter(self.domain, self.subdomains):
            self.search(self.domain, filtered_subdomain=statement)

        if self.recursive:
            for subdomain in self.recursive_subdomain():
                self.search(subdomain)
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = GoogleAPI(domain, config)
    return module.run()
