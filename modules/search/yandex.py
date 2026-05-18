"""
Yandex 搜索模块
"""

import random
import time
from typing import Optional, Set

from common.search import Search
from config.logging import logger


class Yandex(Search):
    """
    Yandex 搜索引擎子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Yandex'
        self.source = 'yandex.com'
        self.init = 'https://yandex.com/'
        self.addr = 'https://yandex.com/search'
        self.limit_num = 1000
        self.per_page_num = 50

    def _is_blocked(self, resp) -> bool:
        """检测反爬虫拦截（含重定向检测）"""
        if not resp or not resp.text:
            return True

        if resp.status_code in (302, 301):
            redirect_url = resp.headers.get('Location', '')
            logger.warning(f'Yandex 请求被重定向: {redirect_url[:100]}')
            return True
        if resp.status_code in (403, 429):
            logger.warning(f'Yandex 请求被拦截，状态码: {resp.status_code}')
            return True

        text_lower = resp.text.lower()
        blocked = ['captcha', 'verify', 'showcaptcha',
                   'blocked', 'unusual traffic', 'access denied',
                   'not a robot', 'verify you are human']
        for kw in blocked:
            if kw in text_lower:
                logger.warning(f'Yandex 返回拦截页面（关键词: {kw}）')
                return True
        return False

    def search(self, domain: str, filtered_subdomain: str = ''):
        """
        发送搜索请求并做子域匹配

        :param str domain: 域名
        :param str filtered_subdomain: 过滤的子域
        """
        self.get_header()
        self.header['Referer'] = 'https://yandex.com/'
        self.proxy = self.get_proxy(self.source)
        self.page_num = 0
        resp = self.get(self.init)
        if not resp or self._is_blocked(resp):
            return
        self.cookie = resp.cookies
        while True:
            time.sleep(random.uniform(8, 15))
            self.proxy = self.get_proxy(self.source)
            self.get_header()
            self.header['Referer'] = 'https://yandex.com/'
            query = 'site:' + domain + filtered_subdomain
            params = {'text': query, 'p': self.page_num,
                      'numdoc': self.per_page_num}
            resp = self.get(self.addr, params)
            if not resp or self._is_blocked(resp):
                return
            subdomains = self.match_subdomains(resp, fuzzy=True)
            subdomains = {s for s in subdomains
                          if not s.lower().startswith('2f')
                          and not s.lower().startswith('%2f')}
            if not self.check_subdomains(subdomains):
                break
            self.subdomains.update(subdomains)
            if '>next</a>' not in resp.text:
                break
            self.page_num += 1
            if self.page_num >= self.limit_num:
                break

    def run(self) -> Set[str]:
        """执行 Yandex 搜索"""
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
    module = Yandex(domain, config)
    return module.run()
