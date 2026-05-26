"""
Yahoo 搜索模块（Playwright 异步）
"""

import asyncio
import random
from typing import Optional, Set
from urllib.parse import urlencode

from common.async_module import AsyncModuleMixin
from common.search import Search
from common.utils import new_browser_context
from config.logging import logger


class Yahoo(Search, AsyncModuleMixin):
    """
    Yahoo 搜索引擎子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Yahoo'
        self.source = 'search.yahoo.com'
        self.init = 'https://search.yahoo.com/'
        self.addr = 'https://search.yahoo.com/search'
        self.limit_num = 1000
        self.per_page_num = 30

    def _is_blocked(self, html: str) -> bool:
        """检测反爬虫拦截"""
        if not html:
            return True
        text_lower = html.lower()
        blocked = ['captcha', 'verify', 'unusual traffic',
                   'are you a human', 'security check', 'challenge',
                   'not a robot', 'verify you are human']
        for kw in blocked:
            if kw in text_lower:
                logger.warning(f'Yahoo 返回拦截页面（关键词: {kw}）')
                return True
        return False

    async def _search_pages(self, page, query: str):
        """
        对指定搜索词进行分页搜索

        :param page: Playwright Page 实例
        :param str query: 搜索关键词
        """
        page_num = 0

        while True:
            await asyncio.sleep(random.uniform(3, 6))
            params = {'p': query, 'b': page_num, 'pz': self.per_page_num}
            search_url = f'{self.addr}?{urlencode(params)}'

            try:
                await page.goto(search_url, timeout=30000, wait_until='domcontentloaded')
            except Exception as e:
                logger.warning(f'Yahoo 搜索请求失败: {e}')
                break

            html = await page.content()

            if self._is_blocked(html):
                break

            subdomains = self.match_subdomains(html, fuzzy=True)
            subdomains = {s for s in subdomains
                          if not s.lower().startswith('2f')
                          and not s.lower().startswith('%2f')}

            if not self.check_subdomains(subdomains):
                break

            self.subdomains.update(subdomains)
            page_num += self.per_page_num

            if '>Next</a>' not in html:
                break
            if page_num >= self.limit_num:
                break

    async def _search_all(self):
        """异步搜索入口，管理浏览器生命周期"""
        self.get_header()
        self.proxy = self.get_proxy(self.source)

        browser, context, pw = await new_browser_context(
            proxy=self.proxy,
            user_agent=self.header.get('User-Agent'),
        )
        if not browser:
            return

        try:
            page = await context.new_page()

            try:
                await page.goto(self.init, timeout=30000, wait_until='domcontentloaded')
            except Exception as e:
                logger.warning(f'Yahoo 首页访问失败: {e}')

            query = f'site:{self.domain}'
            await self._search_pages(page, query)

            for statement in self.filter(self.domain, self.subdomains):
                await self._search_pages(page, f'site:{self.domain} -{statement}')

            if self.recursive:
                for subdomain in self.recursive_subdomain():
                    await self._search_pages(page, f'site:{subdomain}')
        finally:
            # shield 防止 CancelledError 中断清理导致 Playwright 帧分离
            await asyncio.shield(browser.close())
            await asyncio.shield(pw.stop())

    async def run_async(self) -> Set[str]:
        """
        异步执行 Yahoo 搜索（供调度器直接调用）

        :return: 子域名集合
        """
        self.begin()
        await self._search_all()
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains

    def run(self) -> Set[str]:
        """执行 Yahoo 搜索"""
        self.begin()
        asyncio.run(self._search_all())
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = Yahoo(domain, config)
    return module.run()
