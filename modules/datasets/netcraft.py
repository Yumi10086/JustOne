"""
NetCraft 子域查询模块
"""

import hashlib
import re
import time
from typing import Optional, Set
from urllib import parse

from common.module import Module
from config.logging import logger


class NetCraft(Module):
    """
    NetCraft 子域查询接口

    通过 searchdns.netcraft.com 的 site report 查询目标域名的子域名。

    关键机制：
    1. JS Cookie 挑战：Netcraft 对自动化访问有防护，首次访问会设 cookie
       netcraft_js_verification_challenge，需客户端计算 SHA1(unescape(token))
       后通过 netcraft_js_verification_response 回传
    2. 分页：从 HTML 中提取 <A href=...><b>Next page</b></a> 链接
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 NetCraft 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'NetCraft'
        self.source = 'netcraft'
        self.base_url = 'https://searchdns.netcraft.com/'
        self.page_num = 0
        self.cookie = None

    def _bypass_verification(self) -> bool:
        """
        绕过 Netcraft 的 JS Cookie 挑战

        流程（与 OneForAll/recon-ng 一致）：
        1. 访问首页 → 服务器返回 JS 挑战页面 + cookie
        2. 从响应 cookie 中提取 netcraft_js_verification_challenge
        3. URL 解码 challenge 值 → SHA1 哈希
        4. 将原始 challenge cookie + 计算出的 response cookie 存入 self.cookie
        5. 后续所有请求携带这两个 cookie 即可通过验证

        :return: 是否成功绕过挑战
        """
        session = self._get_session()
        try:
            # Step 1: 首次访问获取 challenge cookie（用 session 直连，不走 get() 的代理重试）
            self.header = self.get_header()
            resp = session.get(
                self.base_url,
                headers=self.header,
                timeout=self.timeout,
                verify=self.verify,
            )

            # Step 2: 从 session 的 cookie jar 中提取 challenge token
            challenge = None
            for cookie in session.cookies:
                if cookie.name == 'netcraft_js_verification_challenge':
                    challenge = cookie.value
                    break

            if not challenge:
                logger.debug(f'{self.source} 未检测到 JS 挑战（可能无需验证）')
                return True

            # Step 3: URL 解码 + SHA1 回显
            decoded = parse.unquote(challenge).encode('utf-8')
            response_token = hashlib.sha1(decoded).hexdigest()

            # Step 4: 将两个 cookie 存入 self.cookie，后续 get()/post() 自动携带
            self.cookie = {
                'netcraft_js_verification_challenge': challenge,
                'netcraft_js_verification_response': response_token,
            }

            logger.debug(f'{self.source} JS 挑战验证通过')
            return True

        except Exception as e:
            logger.error(f'{self.source} JS 挑战验证异常: {e}')
            return False

    def _build_search_url(self) -> str:
        """
        构建搜索 URL

        :return: 搜索 URL 字符串
        """
        return f'{self.base_url}?restriction=site+contains&host=*.{self.domain}'

    def _extract_next_page(self, html: str) -> Optional[str]:
        """
        从 HTML 中提取 Next Page 链接

        分页链接格式：
        <A href="/?restriction=site+contains&host=*.example.com&from=21&last=...">
            <b>Next page</b>
        </A>

        :param html: 页面 HTML 文本
        :return: 下一页完整 URL，无 Next Page 时返回 None
        """
        pattern = re.compile(
            r'<[Aa]\s[^>]*href="([^"]*)"[^>]*>.*?<[Bb]>Next [Pp]age', re.DOTALL
        )
        match = pattern.search(html)
        if not match:
            return None
        link = match.group(1)
        # 处理 HTMLEntity 和空格编码
        link = link.replace('&amp;', '&').replace('%20', ' ')
        # 确保 host 参数指向当前目标域名
        link = re.sub(r'host=[^&]*', f'host=*.{self.domain}', link)
        return self.base_url.rstrip('/') + link

    def _setup_headers(self):
        """
        设置请求头

        Netcraft 检测自动化访问，完整请求头提高成功率。
        """
        self.header = self.get_header()
        self.header.update({
            'Referer': 'https://searchdns.netcraft.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def query(self):
        """
        向接口查询子域并做子域匹配

        分页逻辑：
        1. 绕过 JS Cookie 挑战
        2. 首次搜索请求使用 _build_search_url()
        3. 后续从 HTML 提取 Next Page 链接
        4. 无结果或无 Next Page 时退出

        安全保护：
        - 最多 10 页（避免死循环）
        - 每次请求间隔 self.delay 秒
        """
        self._setup_headers()

        # 绕过 JS 挑战
        if not self._bypass_verification():
            logger.error(f'{self.source} 模块 JS 挑战验证失败，跳过')
            return

        url = self._build_search_url()
        max_pages = 10

        while self.page_num < max_pages:
            time.sleep(self.delay)
            self.proxy = self.get_proxy(self.source)

            resp = self.get(url, check=False)
            if not resp:
                logger.error(f'{self.source} 模块请求失败')
                return

            if resp.status_code != 200:
                logger.warning(
                    f'{self.source} 返回状态码 {resp.status_code}'
                )
                return

            # 从响应中提取子域名
            subdomains = self.match_subdomains(resp)
            if not subdomains:
                break

            self.subdomains.update(subdomains)
            self.page_num += 1

            # 提取下一页链接
            next_url = self._extract_next_page(resp.text)
            if not next_url:
                break

            url = next_url

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
    module = NetCraft(domain, config)
    return module.run()
