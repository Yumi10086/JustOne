"""
搜索引擎模块基类
继承 Module，增加搜索引擎专用方法
"""

import re
from typing import Set, List

from common.module import Module
from config.settings import settings


class Search(Module):
    """搜索引擎基类"""

    def __init__(self, domain: str = '', config: dict = None):
        super().__init__(domain, config)
        self.delay = 1
        self.recursive = self.config.get('search_recursive', False)

    def check_subdomains(self, subdomains: Set[str]) -> bool:
        """
        检查是否继续搜索分页

        :param set subdomains: 当前页发现的子域名
        :return: True 继续分页，False 停止
        """
        if not subdomains:
            return False
        return True

    def filter(self, domain: str, subdomains: Set[str]) -> List[str]:
        """
        分析子域名，筛选出现次数过多的子域前缀以便排除后重新搜索

        :param str domain: 主域名
        :param set subdomains: 已发现的子域名集合
        :return: 需要排除的子域名前缀列表
        """
        statements = set()
        subdomains_temp = set()
        for subdomain in subdomains:
            subdomain_temp = subdomain.replace('.' + domain, '')
            result = re.search(r'([a-zA-Z0-9])', subdomain_temp)
            if not result:
                continue
            subdomain_temp = subdomain_temp[:result.end()]
            subdomains_temp.add(subdomain_temp)
        for subdomain_temp in subdomains_temp:
            count = sum(1 for s in subdomains if subdomain_temp in s)
            if count >= 100:
                statements.add(subdomain_temp)
        return list(statements)

    def recursive_subdomain(self) -> Set[str]:
        """
        返回已发现的子域名（用于递归搜索）

        :return: 子域名集合
        """
        return self.subdomains.copy()
