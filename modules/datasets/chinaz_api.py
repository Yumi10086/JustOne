"""
Chinaz API 子域名查询模块
"""

from typing import Optional, Set

from common.module import Module
from config.settings import settings


class ChinazAPI(Module):
    """
    Chinaz API 子域名查询模块

    通过站长工具 API 获取目标域名的 Alexa 子域名信息，需要配置 API 密钥
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 ChinazAPI 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'ChinazAPI'
        self.source = 'chinaz_api'
        self.addr = 'https://apidata.chinaz.com/CallAPI/Alexa'
        self.api = settings.chinaz_api

    def query(self):
        """
        向接口查询子域并做子域匹配
        """
        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)
        params = {'key': self.api, 'domainName': self.domain}
        resp = self.get(self.addr, params)
        self.subdomains = self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        执行 Chinaz API 子域名查询

        :return: 发现的子域名集合
        """
        if not self.have_api(self.api):
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
    module = ChinazAPI(domain, config)
    return module.run()
