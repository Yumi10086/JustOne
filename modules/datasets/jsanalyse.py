"""
JS 资产子域分析模块

抓取目标主站页面，提取其中引用的同域/子域 JS 文件，
从页面源码与 JS 内容中匹配提取子域名。
"""

import re
from typing import Optional, Set
from urllib.parse import urljoin, urlparse

from common.module import Module


class JSAnalyse(Module):
    """
    JS 文件子域分析

    现代 Web 应用的子域常出现在 JS 包内（API 网关、地图服务、埋点域名等）。
    本模块抓取主站首页，解析 <script src=...> 引用，仅抓取属于目标注册域
    及其子域的 JS 文件（避免请求无关第三方 CDN），并对页面源码与 JS 内容
    统一做子域正则匹配。
    """

    SCRIPT_RE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 JSAnalyse 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典（js_max_scripts 控制抓取的 JS 数量上限）
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'JSAnalyse'
        self.source = 'jsfiles'
        self.max_scripts = self.config.get('js_max_scripts', 20)

    def fetch_page(self) -> Optional[str]:
        """
        抓取主站首页（https 优先，失败回退 http）

        :return: 页面 HTML，失败返回 None
        """
        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)
        for scheme in ('https', 'http'):
            resp = self.get(f'{scheme}://{self.domain}/', check=False, ignore=True)
            if resp and resp.text:
                return resp.text
        return None

    def extract_scripts(self, html: str) -> Set[str]:
        """
        提取页面引用的同域/子域 JS 文件绝对地址

        :param str html: 页面 HTML
        :return: JS 文件 URL 集合
        """
        base = f'https://{self.domain}/'
        urls = set()
        for src in self.SCRIPT_RE.findall(html):
            absolute = urljoin(base, src)
            host = urlparse(absolute).hostname or ''
            if host == self.domain or host.endswith('.' + self.domain):
                urls.add(absolute)
        return urls

    def analyse(self):
        """
        执行分析：匹配页面源码 + 抓取并匹配 JS 文件内容
        """
        html = self.fetch_page()
        if not html:
            return

        # 页面源码本身也可能包含子域（接口地址、注释等）
        self.collect_subdomains(html)

        for url in list(self.extract_scripts(html))[:self.max_scripts]:
            resp = self.get(url, check=False, ignore=True)
            if resp and resp.text:
                self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        类统一执行入口

        :return: 子域名集合
        """
        self.begin()
        self.analyse()
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
    module = JSAnalyse(domain, config)
    return module.run()
