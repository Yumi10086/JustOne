"""
LeakIX 数据集查询模块
"""

from typing import Optional, Set

from common.module import Module
from common import utils


class LeakIX(Module):
    """
    LeakIX 数据集查询模块

    通过 LeakIX 公开数据集查询子域名信息
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 LeakIX 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'LeakIX'
        self.source = 'leakix.net'

    def run(self) -> Set[str]:
        """
        执行 LeakIX 数据集查询

        :return: 发现的子域名集合
        """
        self.begin()
        logger = utils.get_logger()

        logger.info(f'开始 LeakIX 数据集查询: {self.domain}')

        try:
            url = 'https://leakix.net/search'
            params = {
                'q': f'subdomain:{self.domain}',
            }
            resp = self.get(url, params=params)

            if resp and resp.text:
                subdomains = self.match_subdomains(resp.text)
                self.subdomains.update(subdomains)
                logger.info(f'LeakIX 查询完成，发现 {len(self.subdomains)} 个子域名')

        except Exception as e:
            logger.warning(f'LeakIX 查询出错: {e}')

        self.finish()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = LeakIX(domain, config)
    module.begin()
    subdomains = module.run()
    module.finish()
    return subdomains