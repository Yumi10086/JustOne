"""
DNS 域传送检查模块

查询域名的 NS 记录，检查域名服务器是否开启 DNS 域传送，
如果开启且未做访问控制和身份验证，则利用该漏洞获取域名的所有记录。
"""

import dns.resolver
import dns.query
import dns.zone

from typing import Optional, Set

from common import utils
from common.module import Module
from config.logging import logger


class AXFR(Module):
    """
    DNS 域传送检查模块

    通过 NS 记录查找域名服务器，尝试进行 DNS 域传送以收集子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 DNS 域传送模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'DNSZoneTransfer'
        self.source = 'axfr_check'
        self.results = []

    def axfr(self, server):
        """
        执行域传送

        :param server: 域名服务器地址
        """
        logger.debug(f'Trying to perform domain transfer in {server} '
                     f'of {self.domain}')
        try:
            xfr = dns.query.xfr(where=server, zone=self.domain,
                                timeout=5.0, lifetime=10.0)
            zone = dns.zone.from_xfr(xfr)
        except Exception as e:
            logger.debug(e.args)
            logger.debug(f'Domain transfer to server {server} of '
                         f'{self.domain} failed')
            return
        names = zone.nodes.keys()
        for name in names:
            full_domain = str(name) + '.' + self.domain
            subdomain = self.match_subdomains(full_domain)
            self.subdomains.update(subdomain)
            record = zone[name].to_text(name)
            self.results.append(record)
        if self.results:
            logger.debug(f'Found the domain transfer record of '
                         f'{self.domain} on {server}')
            logger.debug('\n'.join(self.results))
            self.results = []

    def check(self):
        """
        查询 NS 记录并尝试域传送
        """
        resolver = utils.dns_resolver()
        try:
            answers = resolver.query(self.domain, "NS")
        except Exception as e:
            logger.error(e.args)
            return
        nsservers = [str(answer) for answer in answers]
        if not len(nsservers):
            logger.warning(f'No name server record found for {self.domain}')
            return
        for nsserver in nsservers:
            self.axfr(nsserver)

    def run(self) -> Set[str]:
        """
        执行 DNS 域传送检查

        :return: 发现的子域名集合
        """
        self.begin()
        self.check()
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块统一调用入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = AXFR(domain, config)
    return module.run()
