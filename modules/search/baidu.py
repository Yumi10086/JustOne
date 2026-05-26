"""
百度搜索模块
"""

import random
import time
from typing import Optional, Set

from common.module import Module
from config.logging import logger


class BaiduSearch(Module):
    """
    百度搜索引擎子域收集模块

    通过百度搜索 site: 语法收集子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化百度搜索模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'BaiduSearch'
        self.source = 'baidu.com'

    def _is_blocked(self, resp) -> bool:
        """
        检测是否被反爬虫拦截

        :param resp: 响应对象
        :return: True 被拦截，False 正常
        """
        if not resp or not resp.text:
            return True

        text_lower = resp.text.lower()

        blocked_keywords = ['captcha', 'verify', 'antispider',
                            '请输入验证码', '安全验证',
                            'ip地址异常', '访问受限',
                            'forbidden', 'blocked']
        for kw in blocked_keywords:
            if kw in text_lower:
                logger.warning(f'百度返回了验证/拦截页面（关键词: {kw}）')
                return True

        if resp.status_code in (302, 301, 403, 429):
            logger.warning(f'百度请求被拦截，状态码: {resp.status_code}')
            return True

        if '百度为您找到相关结果' in resp.text and 'result' not in resp.text:
            return False

        if '<div class="result' in resp.text or 'class="result' in resp.text:
            return False

        logger.debug('百度页面中未找到搜索结果，可能为空或反爬虫页面')
        return True

    def run(self) -> Set[str]:
        """
        执行百度搜索子域收集

        :return: 发现的子域名集合
        """
        self.begin()
        self.get_header()

        self.header.update({
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.baidu.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
        })

        self.proxy = self.get_proxy(self.source)

        logger.info('正在访问百度首页获取 Cookie...')
        init_resp = self.get('https://www.baidu.com/', check=False, ignore=True)
        if init_resp and init_resp.cookies:
            self.cookie = init_resp.cookies
            logger.debug('已获取百度 Cookie')

        query = f'site:{self.domain}'
        page_count = 5

        logger.info(f'开始百度搜索收集子域名: {query}')

        # 首次搜索前随机延迟，模拟人工操作
        initial_delay = random.uniform(2, 4)
        logger.debug(f'首次搜索前等待 {initial_delay:.1f}s...')
        time.sleep(initial_delay)

        for page in range(page_count):
            try:
                url = 'https://www.baidu.com/s'
                params = {
                    'wd': query,
                    'pn': page * 10,
                }
                resp = self.get(url, params=params)

                if self._is_blocked(resp):
                    logger.warning('百度反爬虫拦截，停止搜索')
                    break

                if resp and resp.text:
                    subdomains = self.match_subdomains(resp.text)
                    subdomains = {s for s in subdomains
                                  if not s.lower().startswith('2f')
                                  and not s.lower().startswith('%2f')}
                    new_count = len(subdomains)
                    self.subdomains.update(subdomains)
                    logger.info(f'百度搜索第 {page + 1} 页，发现 {new_count} 个子域名')

                    if not subdomains:
                        logger.debug('未发现更多子域名，停止搜索')
                        break

                time.sleep(random.uniform(2, 5))

            except Exception as e:
                logger.warning(f'百度搜索第 {page + 1} 页出错: {e}')

        self.finish()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = BaiduSearch(domain, config)
    return module.run()