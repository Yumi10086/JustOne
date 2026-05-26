"""
RapidDNS 子域查询模块
"""

from typing import Optional, Set

from common.module import Module


class RapidDNS(Module):
    """
    RapidDNS 子域查询接口
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 RapidDNS 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'RapidDNS'
        self.source = 'rapiddns'

    def query(self):
        """
        向接口查询子域并做子域匹配
        """
        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)
        url = f'http://rapiddns.io/subdomain/{self.domain}'
        params = {'full': '1'}
        resp = self.get(url, params)
        self.subdomains = self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        类统一执行入口

        :return: 子域名集合
        """
        self.begin()
        self.query()
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块统一调用入口

    :param domain: 目标域名
    :param config: 可选配置字典
    :return: 子域名集合
    """
    module = RapidDNS(domain, config)
    return module.run()
