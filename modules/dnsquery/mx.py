"""
MX 记录查询模块
"""

from typing import Optional, Set

from common.module import Module
from common import utils
from config.logging import logger


class MXQuery(Module):
    """
    MX 记录查询模块

    查询域名的邮件交换记录
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 MX 查询模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'MXQuery'
        self.source = 'mx_query'

    def run(self) -> Set[str]:
        """
        执行 MX 记录查询

        :return: 发现的子域名集合
        """
        self.begin()

        try:
            answer = utils.dns_query(self.domain, 'MX')
            if answer:
                for rr in answer:
                    mx_str = str(rr).strip('.')
                    parts = mx_str.split()
                    if len(parts) >= 2:
                        mx_domain = parts[1]
                        if mx_domain.endswith(self.domain):
                            self.subdomains.add(mx_domain.lower())
            logger.info(f'MX 查询完成，发现 {len(self.subdomains)} 个子域名')
        except Exception as e:
            logger.error(f'MX 查询出错: {e}')

        self.finish()
        return self.subdomains