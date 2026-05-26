"""
SPF 记录查询模块
"""

import re
from typing import Optional, Set

from common.module import Module
from common import utils
from config.logging import logger


class QuerySPF(Module):
    """
    SPF 记录查询模块

    从 DNS TXT 记录中筛选 SPF（v=spf1）记录，提取包含目标域名的子域名。
    SPF 在 RFC 7208 中已废弃独立 RR 类型，现统一存储在 TXT 记录中。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 SPF 查询模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'QuerySPF'
        self.source = 'QuerySPF'

    def run(self) -> Set[str]:
        """
        执行 SPF 记录查询（从 TXT 记录中提取）

        :return: 发现的子域名集合
        """
        self.begin()

        try:
            answer = utils.dns_query(self.domain, 'TXT')
            if answer:
                regexp = r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.){0,}' + self.domain.replace('.', r'\.')
                for rr in answer:
                    text = ''.join([s.decode() if isinstance(s, bytes) else s for s in rr.strings])
                    if 'v=spf1' not in text.lower():
                        continue
                    matches = re.findall(regexp, text, re.I)
                    for m in matches:
                        self.subdomains.add(m.lower())
            logger.info(f'SPF 查询完成，发现 {len(self.subdomains)} 个子域名')
        except Exception as e:
            logger.error(f'SPF 查询出错: {e}')

        self.finish()
        return self.subdomains
