"""
Censys 证书查询模块

通过 Censys Search API v2 查询证书透明度日志中与目标域名关联的证书，从中提取子域名。
使用 API ID + API Secret 进行 Basic 认证，在 config/.env 中配置 CENSYS_API_ID 和 CENSYS_API_SECRET。
"""

import base64
import time
from typing import Optional, Set

import requests
from config import settings
from common.module import Module
from common import utils


class Censys(Module):
    """
    Censys 证书透明度查询模块

    通过 Censys Search API v2 搜索与目标域名关联的 SSL/TLS 证书，
    从证书的 names 字段中提取子域名。
    需要有效的 Censys API ID 和 API Secret。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 Censys 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Censys'
        self.source = 'censys.io'
        self.addr = 'https://search.censys.io/api/v2/certificates/search'
        self.api_id = settings.censys_api_id
        self.api_secret = settings.censys_api_secret
        self.page_size = 100
        self.max_pages = 3
        self.delay = 1

    def _api_post(self, json_body):
        """
        发送 API POST 请求，直连优先 → 代理兜底

        :param dict json_body: JSON 请求体
        :return: 响应对象，失败返回 None
        """
        session = self._get_session()
        last_error = None
        for attempt in range(self.request_retries):
            proxies = self.proxy if attempt == 1 else None
            try:
                return session.post(self.addr, json=json_body,
                                    headers=self.header,
                                    proxies=proxies,
                                    timeout=self.timeout,
                                    verify=self.verify)
            except (requests.exceptions.ProxyError,
                    requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError) as e:
                last_error = e
                if attempt == 0 and self.proxy:
                    logger = utils.get_logger()
                    logger.debug(f'{self.source} 直连失败，尝试代理: {str(e.args[0])[:80]}')
                    continue
                logger = utils.get_logger()
                logger.error(f'{self.source} 请求异常: {type(e).__name__}: {str(e.args[0])[:100]}')
                return None
            except Exception as e:
                last_error = e
                if attempt == 0 and self.proxy:
                    logger = utils.get_logger()
                    logger.debug(f'{self.source} 直连失败，尝试代理: {str(e.args[0])[:80]}')
                    continue
                logger = utils.get_logger()
                logger.error(f'{self.source} 未知异常: {type(e).__name__}: {str(e.args[0])[:100]}')
                return None
        return None

    def _query(self):
        """
        向 Censys API v2 发送证书搜索请求并提取子域名
        """
        query = f'names: {self.domain}'
        cursor = None
        page = 0

        while page < self.max_pages:
            page += 1
            time.sleep(self.delay)

            self.header = self.get_header()
            auth_raw = f'{self.api_id}:{self.api_secret}'
            auth_b64 = base64.b64encode(auth_raw.encode()).decode()
            self.header['Authorization'] = f'Basic {auth_b64}'
            self.header['Accept'] = 'application/json'
            self.proxy = self.get_proxy(self.source)

            body = {
                'q': query,
                'per_page': self.page_size,
            }
            if cursor:
                body['cursor'] = cursor

            resp = self._api_post(body)

            if not resp:
                logger = utils.get_logger()
                logger.warning(f'{self.source} 请求失败')
                return

            if resp.status_code == 401:
                logger = utils.get_logger()
                logger.warning(f'{self.source} API ID 或 Secret 无效 (401)')
                return

            if resp.status_code == 403:
                logger = utils.get_logger()
                logger.warning(f'{self.source} 无权限访问，请检查 API ID 权限 (403)')
                return

            if resp.status_code == 429:
                logger = utils.get_logger()
                logger.warning(f'{self.source} 请求频率过高 (429)，等待后重试')
                time.sleep(10)
                continue

            if resp.status_code != 200:
                logger = utils.get_logger()
                try:
                    err = resp.json()
                    logger.warning(f'{self.source} API 错误 ({resp.status_code}): {err.get("error", "")}')
                except Exception:
                    logger.error(f'{self.source} 返回错误状态码: {resp.status_code}')
                return

            try:
                data = resp.json()
                code = data.get('code')
                if code and code != 200:
                    logger = utils.get_logger()
                    logger.warning(f'{self.source} API 响应错误 (code={code}): {data.get("error", "未知错误")}')
                    return

                result = data.get('result', {})
                hits = result.get('hits', [])

                logger = utils.get_logger()
                logger.debug(f'{self.source} 第 {page} 页获取到 {len(hits)} 条证书记录')

                for hit in hits:
                    names = hit.get('names', [])
                    if isinstance(names, list):
                        for name in names:
                            if isinstance(name, str):
                                subdomains = self.match_subdomains(name, distinct=True, fuzzy=True)
                                self.subdomains.update(subdomains)

                links = result.get('links', {})
                cursor = links.get('next', '')
                if not cursor:
                    break

            except Exception as e:
                logger = utils.get_logger()
                logger.error(f'{self.source} 解析响应失败: {e}')
                return

    def run(self) -> Set[str]:
        """
        执行 Censys 证书查询

        :return: 发现的子域名集合
        """
        if not self.have_api(self.api_id, self.api_secret):
            return self.subdomains

        self.begin()
        logger = utils.get_logger()

        logger.info(f'开始 Censys 证书查询: {self.domain}')

        try:
            self._query()
            logger.info(f'Censys 查询完成，发现 {len(self.subdomains)} 个子域名')
        except Exception as e:
            logger.error(f'Censys 查询出错: {e}')

        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = Censys(domain, config)
    return module.run()
