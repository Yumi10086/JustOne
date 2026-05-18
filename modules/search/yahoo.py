"""
Yahoo 搜索模块
"""

import random
import time
from typing import Optional, Set

from common.search import Search
from config.logging import logger


class Yahoo(Search):
    """
    Yahoo 搜索引擎子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Yahoo'
        self.source = 'search.yahoo.com'
        self.init = 'https://search.yahoo.com/'
        self.addr = 'https://search.yahoo.com/search'
        self.limit_num = 1000
        self.per_page_num = 30

    def _is_blocked(self, resp) -> bool:
        """检测反爬虫拦截"""
        if not resp or not resp.text:
            return True
        text_lower = resp.text.lower()
        blocked = ['captcha', 'verify', 'unusual traffic',
                   'are you a human', 'security check', 'challenge',
                   'not a robot', 'verify you are human']
        for kw in blocked:
            if kw in text_lower:
                logger.warning(f'Yahoo 返回拦截页面（关键词: {kw}）')
                return True
        if resp.status_code in (302, 403, 429):
            logger.warning(f'Yahoo 请求被拦截，状态码: {resp.status_code}')
            return True
        return False

    def search(self, domain: str, filtered_subdomain: str = ''):
        """
        发送搜索请求并做子域匹配

        :param str domain: 域名
        :param str filtered_subdomain: 过滤的子域
        """
        self.get_header()
        self.header['Referer'] = 'https://search.yahoo.com/'
        self.proxy = self.get_proxy(self.source)
        resp = self.get(self.init)
        if not resp or self._is_blocked(resp):
            return
        self.cookie = resp.cookies
        self.page_num = 0
        while True:
            time.sleep(random.uniform(3, 6))
            self.proxy = self.get_proxy(self.source)
            self.get_header()
            self.header['Referer'] = 'https://search.yahoo.com/'
            query = 'site:' + domain + filtered_subdomain
            params = {'p': query, 'b': self.page_num, 'pz': self.per_page_num}
            resp = self.get(self.addr, params)
            if not resp or self._is_blocked(resp):
                return
            text = resp.text.replace('<b>', '').replace('</b>', '')
            subdomains = self.match_subdomains(text, fuzzy=True)
            subdomains = {s for s in subdomains
                          if not s.lower().startswith('2f')
                          and not s.lower().startswith('%2f')}
            if not self.check_subdomains(subdomains):
                break
            self.subdomains.update(subdomains)
            if '>Next</a>' not in resp.text:
                break
            self.page_num += self.per_page_num
            if self.page_num >= self.limit_num:
                break

    def run(self) -> Set[str]:
        """执行 Yahoo 搜索"""
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
    module = Yahoo(domain, config)
    return module.run()
