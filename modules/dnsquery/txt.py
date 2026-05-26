"""
TXT 记录查询模块
"""

import re
from typing import Optional, Set

from common.module import Module
from common import utils
from config.logging import logger


class QueryTXT(Module):
    """
    TXT 记录查询模块

    利用 DNS 的 TXT 记录收集子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 TXT 查询模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'QueryTXT'
        self.source = 'QueryTXT'

    def run(self) -> Set[str]:
        """
        执行 TXT 记录查询

        :return: 发现的子域名集合
        """
        self.begin()

        try:
            answer = utils.dns_query(self.domain, 'TXT')
            if answer:
                regexp = r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.){0,}' + self.domain.replace('.', r'\.')
                for rr in answer:
                    text = ''.join([s.decode() if isinstance(s, bytes) else s for s in rr.strings])
                    matches = re.findall(regexp, text, re.I)
                    for m in matches:
                        self.subdomains.add(m.lower())
            logger.info(f'TXT 查询完成，发现 {len(self.subdomains)} 个子域名')
        except Exception as e:
            logger.error(f'TXT 查询出错: {e}')

        self.finish()
        return self.subdomains
