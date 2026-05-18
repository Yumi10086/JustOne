"""
Bing 搜索模块
"""

import random
import time
from typing import Optional, Set

from common.module import Module
from config.logging import logger


class BingSearch(Module):
    """
    Bing 搜索引擎子域收集模块

    通过 Bing 搜索 site: 语法收集子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 Bing 搜索模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'BingSearch'
        self.source = 'bing.com'

    def _is_blocked(self, resp) -> bool:
        """
        检测是否被反爬虫拦截

        :param resp: 响应对象
        :return: True 被拦截，False 正常
        """
        if not resp or not resp.text:
            return True

        text_lower = resp.text.lower()

        blocked_keywords = ['captcha', 'verify', 'unusual traffic',
                           'are you a human', 'security check',
                           'access denied', 'blocked']
        for kw in blocked_keywords:
            if kw in text_lower:
                logger.warning(f'Bing 返回了验证/拦截页面（关键词: {kw}）')
                return True

        if resp.status_code in (302, 301, 403, 429):
            logger.warning(f'Bing 请求被拦截，状态码: {resp.status_code}')
            return True

        if 'b_algo' not in resp.text:
            logger.debug('Bing 页面中未找到搜索结果（b_algo 缺失），可能为空或反爬虫页面')
            return True

        return False

    def run(self) -> Set[str]:
        """
        执行 Bing 搜索子域收集

        :return: 发现的子域名集合
        """
        self.begin()
        self.get_header()

        self.header.update({
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Referer': 'https://www.bing.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
        })

        self.proxy = self.get_proxy(self.source)

        logger.info('正在访问 Bing 首页获取 Cookie...')
        init_resp = self.get('https://www.bing.com/', check=False, ignore=True)
        if init_resp and init_resp.cookies:
            self.cookie = init_resp.cookies
            logger.debug('已获取 Bing Cookie')

        query = f'site:{self.domain}'
        page_count = 5

        logger.info(f'开始 Bing 搜索收集子域名: {query}')

        for page in range(page_count):
            try:
                url = 'https://www.bing.com/search'
                params = {
                    'q': query,
                    'first': page * 10 + 1,
                }
                resp = self.get(url, params=params)

                if self._is_blocked(resp):
                    logger.warning('Bing 反爬虫拦截，停止搜索')
                    break

                if resp and resp.text:
                    subdomains = self.match_subdomains(resp.text)
                    subdomains = {s for s in subdomains
                                  if not s.lower().startswith('2f')
                                  and not s.lower().startswith('%2f')}
                    new_count = len(subdomains)
                    self.subdomains.update(subdomains)
                    logger.info(f'Bing 搜索第 {page + 1} 页，发现 {new_count} 个子域名')

                    if not subdomains:
                        logger.debug('未发现更多子域名，停止搜索')
                        break

                time.sleep(random.uniform(3, 6))

            except Exception as e:
                logger.warning(f'Bing 搜索第 {page + 1} 页出错: {e}')

        self.finish()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = BingSearch(domain, config)
    return module.run()