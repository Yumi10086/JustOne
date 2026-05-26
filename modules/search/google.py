"""
Google Web 搜索模块（Playwright 异步）
"""

import asyncio
import random
from typing import Optional, Set
from urllib.parse import urlencode

from common.search import Search
from common.utils import new_browser_context
from config.logging import logger


class Google(Search):
    """
    Google Web 搜索引擎子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'GoogleWeb'
        self.source = 'google.com/web'
        self.init = 'https://www.google.com/'
        self.addr = 'https://www.google.com/search'

    def _is_blocked(self, html: str) -> bool:
        """检测反爬虫拦截"""
        if not html:
            return True
        text_lower = html.lower()
        blocked_kw = ['captcha', 'unusual traffic', 'sorry',
                      'automated queries', "i'm not a robot",
                      'verify you are human', "please show you're not a robot",
                      'our systems have detected unusual traffic',
                      'your client does not have permission']
        for kw in blocked_kw:
            if kw in text_lower:
                logger.warning(f'Google Web 返回拦截页面（关键词: {kw}）')
                return True
        return False

    async def _handle_consent(self, page):
        """处理 Google 同意弹窗"""
        try:
            await page.wait_for_load_state('networkidle', timeout=10000)
        except Exception:
            pass

        consent_selectors = [
            'button:has-text("Accept all")',
            'button:has-text("I agree")',
            'button:has-text("同意")',
            'button:has-text("Accept")',
            '#L2AGLb',
            'form[action*="consent"] button',
        ]
        for selector in consent_selectors:
            try:
                button = await page.wait_for_selector(selector, timeout=3000)
                if button:
                    await button.click()
                    await asyncio.sleep(random.uniform(1, 2))
                    break
            except Exception:
                continue

    async def _search_pages(self, page, word: str):
        """
        对指定搜索词进行分页搜索

        :param page: Playwright Page 实例
        :param str word: 搜索关键词
        """
        page_num = 0
        per_page_num = 50

        while True:
            await asyncio.sleep(random.uniform(3, 7))
            params = {'q': word, 'start': page_num, 'num': per_page_num,
                      'filter': '0', 'hl': 'en'}
            search_url = f'{self.addr}?{urlencode(params)}'

            try:
                await page.goto(search_url, timeout=30000, wait_until='domcontentloaded')
            except Exception as e:
                logger.warning(f'Google Web 搜索请求失败: {e}')
                break

            try:
                await page.wait_for_selector('#search, #res, #rso', timeout=10000)
            except Exception:
                pass

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
            page_num += per_page_num

            if f'start={page_num}' not in html:
                break
            if '302 Moved' in html:
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
                resp = await page.goto(self.init, timeout=30000, wait_until='domcontentloaded')
                if resp and resp.status == 200:
                    await self._handle_consent(page)
            except Exception as e:
                logger.warning(f'Google Web 首页访问失败: {e}')

            await self._search_pages(page, f'site:{self.domain}')

            for statement in self.filter(self.domain, self.subdomains):
                await self._search_pages(page, f'site:{self.domain} -{statement}')

            if self.recursive:
                for subdomain in self.recursive_subdomain():
                    await self._search_pages(page, f'site:{subdomain}')
        finally:
            await browser.close()
            await pw.stop()

    def run(self) -> Set[str]:
        """执行 Google Web 搜索"""
        self.begin()
        asyncio.run(self._search_all())
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = Google(domain, config)
    return module.run()
