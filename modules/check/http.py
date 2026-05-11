"""
HTTP 存活检查模块
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Set

import aiohttp
from tqdm import tqdm

logging.getLogger('aiohttp').setLevel(logging.CRITICAL)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)

from common.module import Module
from common import utils


ALIVE_CODES = {
    200, 201, 202, 203, 204, 205, 206, 207, 208, 226,
    301, 302, 303, 307, 308,
    400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 421, 422, 423, 424, 426, 428, 429, 431, 451,
    500, 501, 502, 503, 504, 505, 506, 507, 508, 510, 511,
}


class AsyncHTTPCheck:
    """
    异步 HTTP 存活检查模块

    使用 aiohttp 进行并发 HTTP 检查
    """

    def __init__(self, domain: str, config: Optional[dict] = None, concurrent: int = 100):
        """
        初始化异步 HTTP 检查模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        :param int concurrent: 并发数
        """
        self.domain = domain
        self.concurrent = concurrent
        self.timeout = config.get('timeout', 5) if config else 5
        self.results = []
        self.infos = {}

    async def check_one(self, subdomain: str, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """检查单个子域名"""
        url = f'http://{subdomain}'
        try:
            async with session.head(url, allow_redirects=False) as resp:
                if resp.status in ALIVE_CODES:
                    return {
                        'subdomain': subdomain,
                        'url': url,
                        'status': resp.status,
                        'alive': True,
                    }
        except Exception:
            pass
        try:
            async with session.get(url, allow_redirects=False) as resp:
                if resp.status in ALIVE_CODES:
                    return {
                        'subdomain': subdomain,
                        'url': url,
                        'status': resp.status,
                        'alive': True,
                    }
        except Exception:
            pass
        return None

    async def run_async(self, subdomains: Set[str], show_progress: bool = True) -> list:
        """
        异步执行 HTTP 存活检查

        :param Set[str] subdomains: 要检查的子域名集合
        :param bool show_progress: 是否显示进度条
        :return: 存活子域名列表
        """
        if not subdomains:
            return []

        total = len(subdomains)
        alive_list = []

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        connector = aiohttp.TCPConnector(limit=self.concurrent, limit_per_host=self.concurrent)

        pbar = None
        last_update_percent = -1

        if show_progress:
            pbar = tqdm(
                total=total,
                desc='HTTP 检查',
                ncols=60,
                mininterval=0.5,
                position=0,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            semaphore = asyncio.Semaphore(self.concurrent)

            async def bounded_check(subdomain: str):
                async with semaphore:
                    return await self.check_one(subdomain, session)

            tasks = [bounded_check(sd) for sd in subdomains]

            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result:
                    alive_list.append(result)
                    self.infos[result['subdomain']] = result

                if show_progress and pbar:
                    pbar.update(1)
                    current_percent = int(pbar.n * 100 / total)
                    if current_percent - last_update_percent >= 5:
                        pbar.refresh()
                        last_update_percent = current_percent

        if show_progress and pbar:
            pbar.close()

        self.results = alive_list
        return alive_list

    def run(self, subdomains: Optional[Set[str]] = None, show_progress: bool = True) -> list:
        """同步入口"""
        return asyncio.run(self.run_async(subdomains or set(), show_progress))


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
            resp = self.head(url, ignore=True)
            if resp:
                status = resp.status_code
                if status in ALIVE_CODES:
                    return {
                        'subdomain': subdomain,
                        'url': url,
                        'status': status,
                        'alive': True,
                    }
            resp = self.get(url, ignore=True)
            if resp:
                status = resp.status_code
                if status in ALIVE_CODES:
                    return {
                        'subdomain': subdomain,
                        'url': url,
                        'status': status,
                        'alive': True,
                    }
        except Exception:
            pass
        return None

    def run(self, subdomains: Optional[Set[str]] = None, show_progress: bool = True) -> list:
        """
        执行 HTTP 存活检查

        :param Set[str] subdomains: 要检查的子域名集合
        :param bool show_progress: 是否显示进度条
        :return: 存活子域名列表
        """
        target_subdomains = subdomains or self.subdomains

        if not target_subdomains:
            return []

        self.subdomains = target_subdomains
        self.begin()

        total = len(target_subdomains)
        alive_list = []

        pbar = None
        last_update_percent = -1

        if show_progress:
            pbar = tqdm(
                total=total,
                desc='HTTP 检查',
                ncols=60,
                mininterval=0.5,
                position=0,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )

        for subdomain in target_subdomains:
            result = self.check(subdomain)
            if result:
                alive_list.append(result)
                self.infos[subdomain] = result

            if show_progress and pbar:
                pbar.update(1)
                current_percent = int(pbar.n * 100 / total)
                if current_percent - last_update_percent >= 5:
                    pbar.refresh()
                    last_update_percent = current_percent

        if show_progress and pbar:
            pbar.close()

        self.subdomains = set(r['subdomain'] for r in alive_list)
        self.finish()
        return alive_list