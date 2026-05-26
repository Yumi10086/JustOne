"""
SOA 记录查询模块
"""

from typing import Optional, Set

from common.module import Module
from common import utils
from config.logging import logger


class QuerySOA(Module):
    """
    SOA 记录查询模块

    利用 DNS 的 SOA 记录收集子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 SOA 查询模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'QuerySOA'
        self.source = 'QuerySOA'

    def run(self) -> Set[str]:
        """
        执行 SOA 记录查询

        :return: 发现的子域名集合
        """
        self.begin()

        try:
            answer = utils.dns_query(self.domain, 'SOA')
            if answer:
                for rr in answer:
                    mname = str(rr.mname).strip('.')
                    if mname.endswith(self.domain):
                        self.subdomains.add(mname.lower())
            logger.info(f'SOA 查询完成，发现 {len(self.subdomains)} 个子域名')
        except Exception as e:
            logger.error(f'SOA 查询出错: {e}')

        self.finish()
        return self.subdomains
