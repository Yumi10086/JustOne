"""
异步 HTTP 请求 Mixin

为 Module 子类提供基于 aiohttp 的异步 HTTP 能力，
与 requests 基类共存，不破坏现有接口。
"""

import asyncio
import random
from typing import Optional

import aiohttp

from config.logging import logger


class AsyncModuleMixin:
    """
    异步 HTTP 请求 Mixin

    使用方式（MRO 要求 Module 在前）:
        class MyMod(Module, AsyncModuleMixin):
            ...
    """

    def __init__(self, *args, **kwargs):
        """Mixin 初始化，必须配合 super().__init__"""
        super().__init__(*args, **kwargs)
        self._async_session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    async def _get_async_session(self) -> aiohttp.ClientSession:
        """
        获取或创建 aiohttp ClientSession（并发安全，双重检查锁）

        :return: aiohttp.ClientSession 实例
        """
        if self._async_session is None:
            async with self._session_lock:
                if self._async_session is None:
                    timeout = aiohttp.ClientTimeout(total=self.timeout)
                    connector = aiohttp.TCPConnector(verify_ssl=self.verify)
                    self._async_session = aiohttp.ClientSession(
                        timeout=timeout,
                        connector=connector,
                    )
        return self._async_session

        async def async_get(
            self, url: str, params: dict = None, check: bool = True,
            ignore: bool = False, **kwargs
        ) -> Optional[str]:
            """
            异步 GET 请求，代理优先(若配置)，直连回退 + 指数退避

        :param str url: 请求 URL
        :param dict params: 查询参数
        :param bool check: 是否校验 HTTP 状态码
        :param bool ignore: 是否降级日志
        :param kwargs: 传递给 aiohttp 的额外参数
        :return: 响应文本，失败返回 None
        """
        level = 'DEBUG' if ignore else 'ERROR'
        session = await self._get_async_session()
        headers = self.header.copy() if self.header else {}
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))

        for attempt in range(self.request_retries):
            proxy = self.proxy if attempt == 0 else None
            backoff = min(2 ** attempt, 30)

            try:
                async with session.get(
                    url, params=params, headers=headers,
                    proxy=proxy, **kwargs
                ) as resp:
                    if check and resp.status not in range(200, 300):
                        logger.debug(
                            f'async_get {url[:80]} 返回状态码 {resp.status}，跳过'
                        )
                        return None
                    return await resp.text()
            except aiohttp.ClientSSLError as e:
                logger.log(level, f'SSL 错误: {str(e)[:100]}')
                return None
            except UnicodeDecodeError as e:
                logger.log(level, f'编码错误: {str(e)[:100]}')
                return None
            except (aiohttp.ClientConnectorError,
                    aiohttp.ClientProxyConnectionError,
                    aiohttp.ServerTimeoutError,
                    asyncio.TimeoutError) as e:
                if attempt == 0:
                    if self.proxy:
                        logger.debug(
                            f'代理失败，{backoff}s 后回退直连: {str(e)[:80]}'
                        )
                        await asyncio.sleep(backoff + random.uniform(0, 1))
                        continue
                    logger.log(level, f'async_get 失败: {str(e)[:100]}')
                    return None
                logger.log(level, f'async_get 失败: {str(e)[:100]}')
                return None
            except Exception as e:
                if attempt == 0:
                    if self.proxy:
                        logger.debug(
                            f'代理失败，{backoff}s 后回退直连: {str(e)[:80]}'
                        )
                        await asyncio.sleep(backoff + random.uniform(0, 1))
                        continue
                    logger.log(level, f'async_get 失败: {str(e)[:100]}')
                    return None
                logger.log(level, f'async_get 失败: {str(e)[:100]}')
                return None

        return None

    async def async_post(
        self, url: str, data: dict = None, check: bool = True,
        **kwargs
    ) -> Optional[str]:
        """
        异步 POST 请求，代理优先(若配置)，直连回退

        :param str url: 请求 URL
        :param dict data: 请求体
        :param bool check: 是否校验 HTTP 状态码
        :param kwargs: 传递给 aiohttp 的额外参数
        :return: 响应文本，失败返回 None
        """
        session = await self._get_async_session()
        headers = self.header.copy() if self.header else {}
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))

        for attempt in range(self.request_retries):
            proxy = self.proxy if attempt == 0 else None
            backoff = min(2 ** attempt, 30)

            try:
                async with session.post(
                    url, data=data, headers=headers,
                    proxy=proxy, **kwargs
                ) as resp:
                    if check and resp.status not in range(200, 300):
                        logger.debug(
                            f'async_post {url[:80]} 返回状态码 {resp.status}'
                        )
                        return None
                    return await resp.text()
            except aiohttp.ClientSSLError as e:
                logger.error(f'SSL 错误: {str(e)[:100]}')
                return None
            except UnicodeDecodeError as e:
                logger.error(f'编码错误: {str(e)[:100]}')
                return None
            except (aiohttp.ClientConnectorError,
                    aiohttp.ServerTimeoutError,
                    asyncio.TimeoutError) as e:
                if attempt == 0:
                    if self.proxy:
                        logger.debug(
                            f'代理失败，{backoff}s 后回退直连: {str(e)[:80]}'
                        )
                        await asyncio.sleep(backoff + random.uniform(0, 1))
                        continue
                    logger.error(f'async_post 失败: {str(e)[:100]}')
                    return None
                logger.error(f'async_post 失败: {str(e)[:100]}')
                return None
            except Exception as e:
                if attempt == 0:
                    if self.proxy:
                        logger.debug(
                            f'代理失败，{backoff}s 后回退直连: {str(e)[:80]}'
                        )
                        await asyncio.sleep(backoff + random.uniform(0, 1))
                        continue
                    logger.error(f'async_post 失败: {str(e)[:100]}')
                    return None
                logger.error(f'async_post 失败: {str(e)[:100]}')
                return None

        return None

    async def async_close(self):
        """关闭 aiohttp ClientSession（并发安全）"""
        async with self._session_lock:
            if self._async_session:
                await self._async_session.close()
                self._async_session = None

    async def run_async(self) -> set:
        """
        异步执行入口（默认实现：to_thread 调用同步 run()）

        异步原生模块（Google/Yahoo 等）应覆盖此方法。
        :return: 子域名集合
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run)

    async def cleanup(self):
        """模块清理钩子（调度器在完成后调用）"""
        await self.async_close()
