"""
Gitee 搜索模块
"""

import random
import time
from typing import Optional, Set

from common.search import Search
from config.logging import logger


class Gitee(Search):
    """
    Gitee 代码搜索子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Gitee'
        self.source = 'gitee.com'
        self.addr = 'https://search.gitee.com/'

    def _is_blocked(self, resp) -> bool:
        """检测反爬虫拦截"""
        if not resp or not resp.text:
            return True
        text_lower = resp.text.lower()
        blocked = ['captcha', 'verify', '异常请求', '验证', '阻断']
        for kw in blocked:
            if kw in text_lower:
                logger.warning(f'Gitee 返回拦截页面（关键词: {kw}）')
                return True
        if resp.status_code in (302, 403, 429):
            logger.warning(f'Gitee 请求被拦截，状态码: {resp.status_code}')
            return True
        return False

    def search(self):
        """向接口查询子域并做子域匹配"""
        self.get_header()
        self.header['Referer'] = 'https://search.gitee.com/'
        self.proxy = self.get_proxy(self.source)

        page_num = 1
        while True:
            time.sleep(random.uniform(2, 5))
            self.get_header()
            self.header['Referer'] = 'https://search.gitee.com/'
            self.proxy = self.get_proxy(self.source)
            params = {'pageno': page_num, 'q': self.domain, 'type': 'code'}
            try:
                resp = self.get(self.addr, params=params)
            except Exception as e:
                logger.error(f'Gitee 请求异常: {e}')
                break
            if self._is_blocked(resp):
                break
            if resp.status_code != 200:
                logger.error(f'{self.source} 查询失败，状态码: {resp.status_code}')
                break
            if 'class="empty-box"' in resp.text:
                break
            subdomains = self.match_subdomains(resp, fuzzy=True)
            if not self.check_subdomains(subdomains):
                break
            self.subdomains.update(subdomains)
            if '<li class="disabled"><a href="###">' in resp.text:
                break
            page_num += 1
            if page_num >= 100:
                break

    def run(self) -> Set[str]:
        """执行 Gitee 搜索"""
        self.begin()
        self.search()
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = Gitee(domain, config)
    return module.run()
