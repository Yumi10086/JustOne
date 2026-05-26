"""
URLScan.io 威胁情报模块
"""

import json
import time
from typing import Optional, Set

from common.module import Module
from config.settings import settings
from config.logging import logger


class URLScan(Module):
    """
    URLScan.io 威胁情报模块

    通过 URLScan.io 搜索 API 获取目标域名的扫描结果，
    从扫描页面的域名关联中提取子域名信息。需要配置 API Key。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 URLScan 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'URLScan'
        self.source = 'urlscan'
        self.api = settings.urlscan_api_key
        self.addr = 'https://urlscan.io/api/v1/search/'
        self.size = 100
        self.min_interval = 2   # URLScan 免费 API 限速

    def query(self):
        """
        查询 URLScan 搜索 API 并提取子域名
        """
        logger.debug(f'{self.source} 等待 {self.min_interval}s 以避免速率限制...')
        time.sleep(self.min_interval)

        self.header = self.get_header()
        self.header.update({'API-Key': self.api})
        self.proxy = self.get_proxy(self.source)
        params = {'q': f'domain:{self.domain}', 'size': self.size}
        resp = self.get(self.addr, params=params)
        if not resp:
            return

        if resp.status_code == 429:
            logger.warning(f'{self.source} 速率限制 (429)，等待 60s 后重试')
            time.sleep(60)
            self.header.update({'API-Key': self.api})
            self.proxy = self.get_proxy(self.source)
            resp = self.get(self.addr, params=params)
            if not resp:
                return
        try:
            data = resp.json()
            results = data.get('results', [])
            for result in results:
                page = result.get('page', {})
                domain = page.get('domain', '')
                if domain and domain.endswith(self.domain):
                    self.subdomains.add(domain)
            logger.debug(f'{self.source} 获取到 {len(results)} 条扫描结果')
        except json.JSONDecodeError:
            logger.warning(f'{self.source} 响应 JSON 解析失败')

    def run(self) -> Set[str]:
        """
        执行 URLScan 子域名查询

        :return: 发现的子域名集合
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
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = URLScan(domain, config)
    return module.run()
