"""
百度搜索模块
"""

import time
from typing import Optional, Set

from common.module import Module
from common import utils


class BaiduSearch(Module):
    """
    百度搜索引擎子域收集模块

    通过百度搜索 site: 语法收集子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化百度搜索模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'BaiduSearch'
        self.source = 'baidu.com'

    def run(self) -> Set[str]:
        """
        执行百度搜索子域收集

        :return: 发现的子域名集合
        """
        self.begin()
        logger = utils.get_logger()

        query = f'site:{self.domain}'
        page_count = 5

        logger.info(f'开始百度搜索收集子域名: {query}')

        for page in range(page_count):
            try:
                url = 'https://www.baidu.com/s'
                params = {
                    'wd': query,
                    'pn': page * 10,
                }
                resp = self.get(url, params=params)
                if resp and resp.text:
                    subdomains = self.match_subdomains(resp.text)
                    new_count = len(subdomains)
                    self.subdomains.update(subdomains)
                    logger.info(f'百度搜索第 {page + 1} 页，发现 {new_count} 个子域名')

                    if not subdomains:
                        logger.debug('未发现更多子域名，停止搜索')
                        break

                time.sleep(2)

            except Exception as e:
                logger.warning(f'百度搜索第 {page + 1} 页出错: {e}')

        self.finish()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = BaiduSearch(domain, config)
    module.begin()
    subdomains = module.run()
    module.finish()
    return subdomains