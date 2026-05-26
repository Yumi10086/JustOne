"""
内容安全策略检查模块

从 HTTP 响应头中的 Content-Security-Policy 字段提取子域名
"""

from typing import Optional, Set

from common.module import Module
from config.logging import logger


class CSP(Module):
    """
    内容安全策略检查模块

    获取域名的 Content-Security-Policy 响应头，从中匹配提取子域名。
    可由外部传入已获取的响应头，也可自行发起 HTTP 请求获取。
    """

    def __init__(self, domain: str, header=None, config: Optional[dict] = None):
        """
        初始化内容安全策略检查模块

        :param str domain: 目标域名
        :param header: 预获取的响应头字典，为 None 时自动请求获取
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'CSP'
        self.source = 'csp_check'
        self.csp_header = header

    @property
    def grab_header(self):
        """
        自动获取 Content-Security-Policy 响应头

        :return: 响应头字典，获取失败返回空字典
        """
        csp_header = dict()
        urls = [f'http://{self.domain}',
                f'https://{self.domain}']
        urls_www = [f'http://www.{self.domain}',
                    f'https://www.{self.domain}']
        header = self.grab_loop(csp_header, urls)
        if header:
            return header
        header = self.grab_loop(csp_header, urls_www)
        return header

    def grab_loop(self, csp_header, urls):
        """
        遍历 URL 列表获取响应头

        :param csp_header: 默认返回的空字典
        :param urls: 要请求的 URL 列表
        :return: 响应头字典
        """
        for url in urls:
            self.header = self.get_header()
            self.proxy = self.get_proxy(self.source)
            response = self.get(url)
            if response:
                return response.headers
        return csp_header

    def check(self):
        """
        正则匹配响应头中的内容安全策略字段以发现子域名
        """
        if not self.csp_header:
            self.csp_header = self.grab_header
        csp = self.csp_header.get('Content-Security-Policy')
        if not self.csp_header:
            logger.debug(f'Failed to get header of {self.domain} domain')
            return
        if not csp:
            logger.debug(f'There is no Content-Security-Policy in the header '
                         f'of {self.domain}')
            return
        self.subdomains = self.match_subdomains(csp)

    def run(self) -> Set[str]:
        """
        执行内容安全策略检查

        :return: 发现的子域名集合
        """
        self.begin()
        self.check()
        self.finish()
        return self.subdomains


def run(domain: str, header=None, config: Optional[dict] = None) -> Set[str]:
    """
    模块统一调用入口

    :param str domain: 目标域名
    :param header: 预获取的响应头字典
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = CSP(domain, header, config)
    return module.run()
