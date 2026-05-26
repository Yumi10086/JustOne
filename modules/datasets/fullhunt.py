"""
FullHunt API 子域名查询模块
"""

from typing import Optional, Set

from common.module import Module
from config.settings import settings


class FullHuntAPI(Module):
    """
    FullHunt API 子域名查询模块

    通过 FullHunt API 获取目标域名的子域名信息，需要配置 API 密钥
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 FullHuntAPI 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'FullHuntAPI'
        self.source = 'fullhunt_api'
        self.api = settings.fullhunt_api_key

    def query(self):
        """
        向接口查询子域并做子域匹配
        """
        self.header = self.get_header()
        self.header.update({'X-API-KEY': self.api})
        self.proxy = self.get_proxy(self.source)
        url = f'https://fullhunt.io/api/v1/domain/{self.domain}/subdomains'
        resp = self.get(url)
        self.subdomains = self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        执行 FullHunt API 子域名查询

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
    module = FullHuntAPI(domain, config)
    return module.run()
