"""
HackerTarget 子域名查询模块
"""

from typing import Optional, Set

from common.module import Module


class HackerTarget(Module):
    """
    HackerTarget 子域名查询模块

    通过 HackerTarget API 获取目标域名的子域名信息
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 HackerTarget 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'HackerTarget'
        self.source = 'hackertarget'
        self.addr = 'https://api.hackertarget.com/hostsearch/'

    def query(self):
        """
        向接口查询子域并做子域匹配
        """
        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)
        params = {'q': self.domain}
        resp = self.get(self.addr, params)
        self.subdomains = self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        执行 HackerTarget 子域名查询

        :return: 发现的子域名集合
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
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = HackerTarget(domain, config)
    return module.run()
