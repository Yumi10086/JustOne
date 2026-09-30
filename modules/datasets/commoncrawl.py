"""
Common Crawl 开放索引子域收集模块
"""

import json
from typing import Optional, Set

from config.logging import logger
from common.module import Module


class CommonCrawl(Module):
    """
    Common Crawl 子域收集

    取最新索引段，按 *.domain 拉取命中的 URL 并匹配子域名；
    单页无新增时停止翻页。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 CommonCrawl 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'CommonCrawl'
        self.source = 'index.commoncrawl.org'
        self.addr = 'https://index.commoncrawl.org'
        self.max_pages = self.config.get('cc_max_pages', 2)

    def get_latest_index(self) -> Optional[str]:
        """
        获取最新索引段的 CDX API 地址（如 CC-MAIN-2025-30-index）

        :return: CDX API 基址，失败返回 None
        """
        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)
        resp = self.get(f'{self.addr}/collinfo.json', check=False, ignore=True)
        if not resp or not resp.text:
            return None
        try:
            colls = json.loads(resp.text)
            # collinfo 按时间倒序，第一个即最新索引段
            return colls[0]['cdx-api']
        except (ValueError, KeyError, IndexError, TypeError) as e:
            logger.debug(f'解析 Common Crawl collinfo 失败: {e}')
            return None

    def query(self):
        """
        查询 Common Crawl CDX API 并做子域匹配
        """
        api = self.get_latest_index()
        if not api:
            logger.debug('未获取到 Common Crawl 索引段，跳过')
            return

        for page in range(self.max_pages):
            params = {
                'url': f'*.{self.domain}',
                'output': 'json',
                'page': str(page),
            }
            resp = self.get(f'{api}/index', params=params, check=False, ignore=True)
            if not resp or not resp.text:
                break
            before = len(self.subdomains)
            self.collect_subdomains(resp)
            # 当前页无新增子域则提前停止
            if len(self.subdomains) == before:
                break

    def run(self) -> Set[str]:
        """
        类统一执行入口

        :return: 子域名集合
        """
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
    module = CommonCrawl(domain, config)
    return module.run()
