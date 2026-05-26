"""
CertSpotter 证书透明度查询模块
"""

import json
from typing import Optional, Set

from common.module import Module
from common import utils


class CertSpotter(Module):
    """
    CertSpotter 证书透明度查询模块

    通过查询 api.certspotter.com 获取目标域名的证书信息
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 CertSpotter 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'CertSpotter'
        self.source = 'certspotter.com'
        self.addr = 'https://api.certspotter.com/v1/issuances'

    def _query(self):
        """
        向接口查询子域并做子域匹配
        """
        self.get_header()
        self.proxy = self.get_proxy(self.source)
        params = {
            'domain': self.domain,
            'include_subdomains': 'true',
            'expand': 'dns_names',
        }
        resp = self.get(self.addr, params)

        if resp and resp.text:
            try:
                data = json.loads(resp.text)
                for cert in data:
                    dns_names = cert.get('dns_names', [])
                    if isinstance(dns_names, list):
                        for name in dns_names:
                            subdomains = self.match_subdomains(name, distinct=True, fuzzy=True)
                            self.subdomains.update(subdomains)
            except json.JSONDecodeError:
                self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        执行 CertSpotter 证书查询

        :return: 发现的子域名集合
        """
        self.begin()
        logger = utils.get_logger()

        logger.info(f'开始 CertSpotter 证书查询: .{self.domain}')

        try:
            self._query()
            logger.info(f'CertSpotter 查询完成，发现 {len(self.subdomains)} 个子域名')
        except Exception as e:
            logger.error(f'CertSpotter 查询出错: {e}')

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
    module = CertSpotter(domain, config)
    return module.run()
