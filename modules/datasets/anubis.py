"""
Anubis 子域名查询模块
"""

from typing import Optional, Set

from common.module import Module
from config.logging import logger


class Anubis(Module):
    """
    Anubis 子域名查询模块

    通过 Anubis API 获取目标域名的子域名信息
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 Anubis 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Anubis'
        self.source = 'anubis'
        self.addr = 'https://jldc.me/anubis/subdomains/'

    def query(self):
        """
        向接口查询子域并做子域匹配
        """
        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)
        url = self.addr + self.domain
        resp = self.get(url, check=False)
        if not resp:
            return
        if resp.status_code != 200:
            logger.warning(f'{self.source} 返回状态码 {resp.status_code}，可能已被 Cloudflare 等防护拦截')
            return
        self.subdomains = self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        执行 Anubis 子域名查询

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
    module = Anubis(domain, config)
    return module.run()
