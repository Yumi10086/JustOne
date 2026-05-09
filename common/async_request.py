"""
异步 HTTP 请求模块
"""

import asyncio
from typing import Optional

import aiohttp


class AsyncRequest:
    """异步 HTTP 请求封装类"""

    def __init__(self, timeout: int = 27, max_retries: int = 3):
        """
        初始化异步请求对象

        :param int timeout: 超时时间（秒）
        :param int max_retries: 最大重试次数
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """进入上下文管理器，创建 session"""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, *args):
        """退出上下文管理器，关闭 session"""
        if self.session:
            await self.session.close()

    async def get(self, url: str, **kwargs) -> Optional[aiohttp.ClientResponse]:
        """
        发送 GET 请求

        :param str url: 请求 URL
        :param kwargs: 其他参数
        :return: 响应文本，失败返回 None
        """
        for _ in range(self.max_retries):
            try:
                async with self.session.get(url, **kwargs) as resp:
                    if resp.status == 200:
                        return await resp.text()
            except Exception:
                await asyncio.sleep(1)
        return None