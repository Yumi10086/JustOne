"""
360 搜索模块
"""

import time
from typing import Optional, Set

from common.module import Module
from config.logging import logger


class SoSearch(Module):
    """
    360 搜索引擎子域收集模块

    通过 360 搜索 site: 语法收集子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 360 搜索模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'SoSearch'
        self.source = 'so.com'
        self.addr = 'https://www.so.com/s'
        self.per_page_num = 10
        self.limit_num = 640

    def run(self) -> Set[str]:
        """
        执行 360 搜索子域收集

        :return: 发现的子域名集合
        """
        self.begin()
        self.get_header()
        self.proxy = self.get_proxy(self.source)

        query = f'site:{self.domain}'
        logger.info(f'开始 360 搜索收集子域名: {query}')

        page_num = 1
        while True:
            time.sleep(self.delay)
            self.header = self.get_header()
            self.proxy = self.get_proxy(self.source)

            payload = {'q': query, 'pn': page_num}
            resp = self.get(self.addr, params=payload)

            if not resp or not resp.text:
                break

            subdomains = self.match_subdomains(resp.text, fuzzy=False)
            if not subdomains:
                break

            self.subdomains.update(subdomains)
            logger.info(f'360 搜索第 {page_num} 页，发现 {len(subdomains)} 个子域名')

            if '<a id="snext"' not in resp.text:
                break

            page_num += 1
            if page_num * self.per_page_num >= self.limit_num:
                break

        self.finish()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = SoSearch(domain, config)
    return module.run()
