"""
DNS 解析验证模块
"""

from typing import Optional, Dict, Any, Set

from common.module import Module
from common import resolve
from common import utils


class DNSCheck(Module):
    """
    DNS 解析验证模块

    验证子域名是否可以正常解析
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 DNS 检查模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'DNSCheck'
        self.source = 'dns_check'

    def check(self, subdomain: str) -> Optional[Dict[str, Any]]:
        """
        检查单个子域名的 DNS 解析

        :param str subdomain: 子域名
        :return: 解析结果字典，解析失败返回 None
        """
        try:
            info = resolve.resolve_domain(subdomain)
            if info and info.get('ip'):
                return {
                    'subdomain': subdomain,
                    'ip': info['ip'],
                    'resolve': True,
                }
        except Exception as e:
            logger = utils.get_logger()
            logger.debug(f'{subdomain} DNS 解析失败: {e}')
        return None

    def run(self, subdomains: Optional[Set[str]] = None) -> list:
        """
        执行 DNS 解析验证

        :param Set[str] subdomains: 要检查的子域名集合
        :return: 可解析的子域名列表
        """
        target_subdomains = subdomains or self.subdomains

        if not target_subdomains:
            return []

        self.subdomains = target_subdomains
        self.begin()

        resolved_list = []
        for subdomain in target_subdomains:
            result = self.check(subdomain)
            if result:
                resolved_list.append(result)
                self.infos[subdomain] = result

        self.subdomains = set(r['subdomain'] for r in resolved_list)
        self.finish()
        return resolved_list