"""
Wayback Machine 历史存档子域收集模块
"""

from typing import Optional, Set

from common.module import Module


class Wayback(Module):
    """
    Internet Archive Wayback Machine 子域收集

    通过 CDX 接口拉取目标域名的历史抓取 URL，从中匹配提取子域名。
    历史存档数据对已下线/改版的资产覆盖好，是被动收集的高性价比来源。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 Wayback 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'Wayback'
        self.source = 'web.archive.org'
        self.addr = 'https://web.archive.org/cdx/search/cdx'

    def query(self):
        """
        查询 Wayback CDX 接口并做子域匹配

        分别查询泛子域与主域两条路径，合并结果。
        """
        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)
        base_params = {
            'output': 'json',
            'fl': 'original',
            'collapse': 'urlkey',
            'limit': '20000',
        }
        for url_pattern in (f'*.{self.domain}/*', f'{self.domain}/*'):
            params = dict(base_params, url=url_pattern)
            resp = self.get(self.addr, params=params, check=False, ignore=True)
            if resp and resp.text:
                self.collect_subdomains(resp)

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
    module = Wayback(domain, config)
    return module.run()
