"""
NSEC 记录遍历模块

通过 DNS NSEC 记录进行域遍历（Zone Walking），逐级查询 NSEC 记录以收集子域名。

参考：
https://www.icann.org/resources/pages/dnssec-what-is-it-why-important-2019-03-20-zh
https://appsecco.com/books/subdomain-enumeration/active_techniques/zone_walking.html
"""

from typing import Optional, Set

from common import utils
from common.module import Module


class NSEC(Module):
    """
    NSEC 记录遍历模块

    通过 NSEC 记录链接进行 DNS 域遍历，逐级发现子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 NSEC 遍历模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'NSEC'
        self.source = 'nsec_check'

    def walk(self):
        """
        通过 NSEC 记录进行域遍历，逐级查询子域名
        """
        domain = self.domain
        while True:
            answer = utils.dns_query(domain, 'NSEC')
            if answer is None:
                break
            subdomain = str()
            for item in answer:
                record = item.to_text()
                subdomains = self.match_subdomains(record)
                subdomain = ''.join(subdomains)
                self.subdomains.update(subdomains)
            if subdomain == self.domain:
                break
            if domain != self.domain:
                if domain.split('.')[0] == subdomain.split('.')[0]:
                    break
            domain = subdomain
        return self.subdomains

    def run(self) -> Set[str]:
        """
        执行 NSEC 域遍历

        :return: 发现的子域名集合
        """
        self.begin()
        self.walk()
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
    module = NSEC(domain, config)
    return module.run()
