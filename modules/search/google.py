"""
Google 搜索模块
"""

import random
import time
from typing import Optional, Set

from common.search import Search
from config.logging import logger


class Google(Search):
    """
    Google 搜索引擎子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Google'
        self.source = 'google.com'
        self.init = 'https://www.google.com/'
        self.addr = 'https://www.google.com/search'

    def _is_blocked(self, resp) -> bool:
        """检测反爬虫拦截"""
        if not resp or not resp.text:
            return True
        if resp.status_code in (302, 301, 403, 429):
            logger.warning(f'Google 请求被拦截，状态码: {resp.status_code}')
            return True
        text_lower = resp.text.lower()
        blocked = ['captcha', 'unusual traffic', 'sorry',
                   'automated queries', "i'm not a robot",
                   'verify you are human']
        for kw in blocked:
            if kw in text_lower:
                logger.warning(f'Google 返回拦截页面（关键词: {kw}）')
                return True
        return False

    def search(self, domain: str, filtered_subdomain: str = ''):
        """
        发送搜索请求并做子域匹配

        :param str domain: 域名
        :param str filtered_subdomain: 过滤的子域
        """
        page_num = 1
        per_page_num = 50
        self.get_header()
        self.header.update({'Referer': 'https://www.google.com'})
        self.proxy = self.get_proxy(self.source)
        resp = self.get(self.init)
        if not resp or self._is_blocked(resp):
            return
        self.cookie = resp.cookies
        while True:
            self.delay = random.randint(2, 6)
            time.sleep(self.delay)
            self.proxy = self.get_proxy(self.source)
            word = 'site:' + domain + filtered_subdomain
            payload = {'q': word, 'start': page_num, 'num': per_page_num,
                       'filter': '0', 'btnG': 'Search', 'gbv': '1', 'hl': 'en'}
            resp = self.get(url=self.addr, params=payload)
            if self._is_blocked(resp):
                break
            subdomains = self.match_subdomains(resp, fuzzy=True)
            subdomains = {s for s in subdomains
                          if not s.lower().startswith('2f')
                          and not s.lower().startswith('%2f')}
            if not self.check_subdomains(subdomains):
                break
            self.subdomains.update(subdomains)
            page_num += per_page_num
            if 'start=' + str(page_num) not in resp.text:
                break
            if '302 Moved' in resp.text:
                break

    def run(self) -> Set[str]:
        """执行 Google 搜索"""
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
    module = Google(domain, config)
    return module.run()
