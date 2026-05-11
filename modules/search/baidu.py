"""
百度搜索模块
"""

from typing import Optional, Set

from common.module import Module
from common import utils


class BaiduSearch(Module):
    """
    百度搜索引擎子域收集模块
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
        self.encoder = None

    def run(self) -> Set[str]:
        """
        执行百度搜索子域收集

        :return: 发现的子域名集合
        """
        self.begin()
        logger = utils.get_logger()

        query = f'site:{self.domain}'
        page_count = 10

        for page in range(page_count):
            try:
                url = f'https://www.baidu.com/s'
                params = {
                    'wd': query,
                    'pn': page * 10,
                }
                resp = self.get(url, params=params)
                if resp:
                    subdomains = self.match_subdomains(resp.text)
                    self.subdomains.update(subdomains)
                    logger.debug(f'百度搜索第 {page + 1} 页，发现 {len(subdomains)} 个子域名')
            except Exception as e:
                logger.error(f'百度搜索出错: {e}')

        self.finish()
        return self.subdomains