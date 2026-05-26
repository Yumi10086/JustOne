"""
微步在线 ThreatBook 威胁情报模块
"""

import json
import time
from typing import Optional, Set

from common.module import Module
from config.settings import settings
from config.logging import logger


class ThreatBook(Module):
    """
    微步在线 ThreatBook 威胁情报模块

    通过微步在线云 API 获取目标域名的子域名信息。
    需要配置 API Key，API 文档: https://api.threatbook.cn/v3/domain/sub_domains
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 ThreatBook 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'ThreatBook'
        self.source = 'threatbook'
        self.api = settings.threatbook_api_key
        self.addr = 'https://api.threatbook.cn/v3/domain/sub_domains'
        self.lang = 'zh'
        self.min_interval = 1   # 微步商业 API 限速较宽松

    def query(self):
        """
        查询微步在线子域名 API 并提取子域名
        """
        logger.debug(f'{self.source} 等待 {self.min_interval}s 以避免速率限制...')
        time.sleep(self.min_interval)

        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)
        params = {
            'apikey': self.api,
            'resource': self.domain,
            'lang': self.lang,
        }
        resp = self.get(self.addr, params=params)
        if not resp:
            return

        if resp.status_code == 429:
            logger.warning(f'{self.source} 速率限制 (429)，等待 60s 后重试')
            time.sleep(60)
            self.proxy = self.get_proxy(self.source)
            resp = self.get(self.addr, params=params)
            if not resp:
                return
        try:
            data = resp.json()
            response_code = data.get('response_code')
            if response_code != 0:
                verbose_msg = data.get('verbose_msg', 'Unknown error')
                logger.warning(f'{self.source} API 返回错误: code={response_code}, msg={verbose_msg}')
                return
            sub_domains = data.get('data', {}).get('sub_domains', {})
            total = sub_domains.get('total', '0')
            domains = sub_domains.get('data', [])
            for domain in domains:
                if domain and domain.endswith(self.domain):
                    self.subdomains.add(domain)
            logger.debug(f'{self.source} 获取到 {len(domains)} 个子域名 (总计 {total})')
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.warning(f'{self.source} 响应解析失败: {e}')

    def run(self) -> Set[str]:
        """
        执行微步在线子域名查询

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
    module = ThreatBook(domain, config)
    return module.run()
