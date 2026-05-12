"""
LeakIX 数据集查询模块
"""

from typing import Optional, Set

import requests

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

        api_key = self.config.get('LEAKIX_API') if self.config else None
        if not api_key:
            logger.warning('LeakIX API key 未配置')
            self.finish()
            return self.subdomains

        try:
            url = f'https://leakix.net/api/subdomains/{self.domain}'
            headers = {
                'api-key': api_key,
                'accept': 'application/json'
            }
            resp = requests.get(url, headers=headers, timeout=self.timeout)

            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    subdomain = item.get('subdomain')
                    if subdomain:
                        self.subdomains.add(subdomain.lower())
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
    return module.run()