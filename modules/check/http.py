"""
HTTP 存活检查模块
"""

from typing import Optional, Dict, Any, Set

from common.module import Module
from common import utils


class HTTPCheck(Module):
    """
    HTTP 存活检查模块

    检查子域名是否可访问，获取标题和状态码等信息
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 HTTP 检查模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'HTTPCheck'
        self.source = 'http_check'

    def check(self, subdomain: str) -> Optional[Dict[str, Any]]:
        """
        检查单个子域名

        :param str subdomain: 子域名
        :return: 检查结果字典，未存活返回 None
        """
        url = f'http://{subdomain}'
        try:
            resp = self.head(url, timeout=self.timeout)
            if resp and resp.status_code < 500:
                return {
                    'subdomain': subdomain,
                    'url': url,
                    'status': resp.status_code,
                    'alive': True,
                }
            resp = self.get(url, timeout=self.timeout)
            if resp and resp.status_code < 500:
                return {
                    'subdomain': subdomain,
                    'url': url,
                    'status': resp.status_code,
                    'alive': True,
                }
        except Exception:
            pass
        return None

    def run(self, subdomains: Optional[Set[str]] = None) -> list:
        """
        执行 HTTP 存活检查

        :param Set[str] subdomains: 要检查的子域名集合
        :return: 存活子域名列表
        """
        self.begin()
        target_subdomains = subdomains or self.subdomains

        alive_list = []
        for subdomain in target_subdomains:
            result = self.check(subdomain)
            if result:
                alive_list.append(result)
                self.infos[subdomain] = result

        self.finish()
        return alive_list