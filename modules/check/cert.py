"""
SSL 证书信息检查模块

通过连接目标域名的 443 端口获取 SSL 证书，从证书信息中匹配提取子域名
"""

import socket
import ssl

from typing import Optional, Set

from common.module import Module
from config.logging import logger


class CertInfo(Module):
    """
    SSL 证书信息检查模块

    获取域名的 SSL 证书，匹配证书中的 Subject Alternative Name 等字段以发现子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化证书信息检查模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'CertInfo'
        self.source = 'ssl_cert'

    def check(self):
        """
        获取域名证书并匹配证书中的子域名
        """
        try:
            ctx = ssl.create_default_context()
            sock = socket.socket()
            sock.settimeout(10)
            wrap_sock = ctx.wrap_socket(sock, server_hostname=self.domain)
            wrap_sock.connect((self.domain, 443))
            cert_dict = wrap_sock.getpeercert()
        except Exception as e:
            logger.debug(e.args)
            return
        subdomains = self.match_subdomains(str(cert_dict))
        self.subdomains.update(subdomains)

    def run(self) -> Set[str]:
        """
        执行 SSL 证书信息检查

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
    module = CertInfo(domain, config)
    return module.run()
