"""
SecurityTrails API 子域查询模块

通过 SecurityTrails (Recorded Future) API 获取目标域名的子域名。
认证方式：HTTP Header `APIKEY: xxx`（非 URL 参数）。
免费额度：50 次/月。
"""

import time
from typing import Optional, Set

from config.settings import settings
from config.logging import logger
from common.module import Module


class SecurityTrailsAPI(Module):
    """
    SecurityTrails API 子域查询接口

    API 端点：GET /v1/domain/{domain}/subdomains
    分页方式：scroll_id 参数
    文档：https://docs.securitytrails.com/reference/domain-subdomains
    """

    BASE_URL = 'https://api.securitytrails.com/v1'

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 SecurityTrails API 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'SecurityTrailsAPI'
        self.source = 'securitytrails_api'
        self.api = settings.securitytrails_api

    def _setup_headers(self):
        """
        设置请求头

        SecurityTrails 通过 HTTP Header 认证（非 URL 参数）：
        APIKEY: your_key
        """
        self.header = self.get_header()
        self.header.update({
            'APIKEY': self.api,
            'Content-Type': 'application/json',
        })

    def _query_page(self, scroll_id: str = None) -> tuple:
        """
        查询单页子域名

        :param str scroll_id: 分页滚动 ID（首次为 None）
        :return: (子域名全称集合, 下一页 scroll_id, 总数量)
        """
        url = f'{self.BASE_URL}/domain/{self.domain}/subdomains'
        params = {}
        if scroll_id:
            params['scroll_id'] = scroll_id

        resp = self.get(url, params=params, check=False)
        if not resp:
            logger.warning(f'{self.source} 无响应')
            return set(), None, 0

        if resp.status_code == 401:
            logger.error(f'{self.source} API Key 无效或已过期')
            return set(), None, 0
        if resp.status_code == 403:
            logger.error(f'{self.source} 访问被拒绝（可能免费额度已用完）')
            return set(), None, 0
        if resp.status_code == 429:
            logger.warning(f'{self.source} 频率限制，等待 60 秒后重试')
            time.sleep(60)
            return self._query_page(scroll_id)
        if resp.status_code != 200:
            logger.warning(f'{self.source} 返回状态码 {resp.status_code}')
            return set(), None, 0

        try:
            data = resp.json()
        except Exception as e:
            logger.warning(f'{self.source} JSON 解析失败: {e}')
            return set(), None, 0

        subdomains = set()
        prefixes = data.get('subdomains', [])
        subdomain_count = data.get('subdomain_count', 0)
        next_scroll_id = data.get('scroll_id')

        for prefix in prefixes:
            if not prefix or prefix.startswith('*'):
                continue
            subdomains.add(f'{prefix}.{self.domain}'.lower())

        logger.info(
            f'{self.source} 获取 {len(prefixes)} 条，'
            f'总计 {subdomain_count} 个，'
            f'scroll_id: {bool(next_scroll_id)}'
        )

        return subdomains, next_scroll_id, subdomain_count

    def query(self):
        """
        查询所有子域名（支持 scroll_id 分页）
        """
        self._setup_headers()
        self.proxy = self.get_proxy(self.source)

        scroll_id = None
        page = 0
        max_pages = 100

        while page < max_pages:
            time.sleep(self.delay)
            subdomains, scroll_id, total = self._query_page(scroll_id)
            self.subdomains.update(subdomains)
            page += 1

            if not scroll_id or len(self.subdomains) >= total:
                break

        logger.info(
            f'{self.source} 总计发现 {len(self.subdomains)} 个子域名'
        )

    def run(self) -> Set[str]:
        """
        类统一执行入口

        :return: 子域名集合
        """
        if not self.have_api(self.api):
            return self.subdomains
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
    module = SecurityTrailsAPI(domain, config)
    return module.run()
