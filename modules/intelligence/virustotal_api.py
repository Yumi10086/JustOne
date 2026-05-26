"""
VirusTotal API v3 威胁情报模块

通过 VirusTotal API v3 获取目标域名的子域名信息。
使用游标分页遍历所有结果，内置速率限制保护。
"""

import json
import time
from typing import Optional, Set
from urllib.parse import urlparse, parse_qs

from common.module import Module
from config.settings import settings
from config.logging import logger


class VirusTotalAPI(Module):
    """
    VirusTotal API v3 威胁情报模块

    通过 VirusTotal Domains API v3 获取目标域名的子域名列表。
    需要配置 API Key，免费版限制 4 req/min、500 req/day。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 VirusTotalAPI 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'VirusTotalAPI'
        self.source = 'virustotal'
        self.api = settings.virustotal_api_key
        self.addr = f'https://www.virustotal.com/api/v3/domains/{self.domain}/subdomains'
        self.page_size = 40         # VT API v3 最大 40
        self.max_pages = settings.virustotal_max_pages
        self.page_delay = settings.virustotal_page_delay

    def _query(self):
        """
        向 VirusTotal API v3 发送请求，游标分页遍历所有子域名
        """
        self.header = self.get_header()
        self.header.update({'x-apikey': self.api})
        self.proxy = self.get_proxy(self.source)

        cursor = None
        page = 0
        total_expected = None

        while page < self.max_pages:
            if page > 0:
                logger.debug(f'{self.source} 等待 {self.page_delay}s 避免速率限制...')
                time.sleep(self.page_delay)

            params = {'limit': self.page_size}
            if cursor:
                params['cursor'] = cursor

            resp = self.get(self.addr, params=params)
            if not resp:
                return

            if resp.status_code == 401:
                logger.warning(f'{self.source} API Key 无效 (401)')
                return

            if resp.status_code == 403:
                logger.warning(f'{self.source} 无权限访问 (403)')
                return

            if resp.status_code == 429:
                logger.warning(f'{self.source} 速率限制 (429)，等待 60s 后重试')
                time.sleep(60)
                continue

            if resp.status_code != 200:
                logger.warning(f'{self.source} 返回状态码 {resp.status_code}')
                return

            try:
                data = resp.json()

                if total_expected is None:
                    meta = data.get('meta', {})
                    total_expected = meta.get('count', 0)
                    logger.debug(f'{self.source} 总计 {total_expected} 条子域名记录')

                items = data.get('data', [])
                page += 1
                logger.debug(f'{self.source} 第 {page} 页获取到 {len(items)} 条记录')

                for item in items:
                    subdomain = item.get('id', '')
                    if subdomain and subdomain.endswith(self.domain):
                        self.subdomains.add(subdomain)

                # 检查下一页
                links = data.get('links', {})
                next_link = links.get('next', '')
                if not next_link:
                    break

                parsed = urlparse(next_link)
                cursor_list = parse_qs(parsed.query).get('cursor', [])
                cursor = cursor_list[0] if cursor_list else None
                if not cursor:
                    break

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f'{self.source} 响应解析失败: {e}')
                return

    def run(self) -> Set[str]:
        """
        执行 VirusTotal API v3 子域名查询

        :return: 发现的子域名集合
        """
        if not self.have_api(self.api):
            return self.subdomains
        self.begin()
        self._query()
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
    module = VirusTotalAPI(domain, config)
    return module.run()
