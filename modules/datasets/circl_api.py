"""
CIRCL 被动 DNS 查询模块
"""

from typing import Optional, Set

from common.module import Module
from config.settings import settings


class CirclAPI(Module):
    """
    CIRCL 被动 DNS 查询模块

    通过 CIRCL 被动 DNS 接口获取目标域名的子域名信息，需要配置用户名和密码
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 CirclAPI 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'CirclAPI'
        self.source = 'circl_api'
        self.addr = 'https://www.circl.lu/pdns/query/'
        self.user = settings.circl_username
        self.pwd = settings.circl_password

    def query(self):
        """
        向接口查询子域并做子域匹配
        """
        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)
        resp = self.get(self.addr + self.domain, auth=(self.user, self.pwd))
        self.subdomains = self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        执行 CIRCL 被动 DNS 查询

        :return: 发现的子域名集合
        """
        if not self.have_api(self.user, self.pwd):
            return self.subdomains
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
    module = CirclAPI(domain, config)
    return module.run()
