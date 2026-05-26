"""
ThreatMiner 威胁情报模块
"""

import time
from typing import Optional, Set

from common.module import Module
from config.logging import logger


class ThreatMiner(Module):
    """
    ThreatMiner 威胁情报模块

    通过 ThreatMiner API v2 获取目标域名的子域名信息。
    无需认证，免费使用，限速 10 queries/minute。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 ThreatMiner 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'ThreatMiner'
        self.source = 'threatminer'
        self.addr = f'https://api.threatminer.org/v2/domain.php?q={self.domain}&rt=5'
        self.min_interval = 7  # 10 req/min → 6s 最小间隔，取 7s 留余量

    def query(self):
        """
        查询 ThreatMiner 子域名 API 并提取子域名
        """
        logger.debug(f'{self.source} 等待 {self.min_interval}s 以避免速率限制...')
        time.sleep(self.min_interval)

        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)

        resp = self.get(self.addr)
        if not resp:
            return

        if resp.status_code == 429:
            logger.warning(f'{self.source} 速率限制 (429)，等待 60s 后重试')
            time.sleep(60)
            self.proxy = self.get_proxy(self.source)
            resp = self.get(self.addr)
            if not resp:
                return

        try:
            data = resp.json()
            status_code = data.get('status_code')

            if status_code == '200':
                results = data.get('results', [])
                for subdomain in results:
                    if subdomain and isinstance(subdomain, str):
                        if subdomain.endswith(self.domain) or f'.{self.domain}' in subdomain:
                            self.subdomains.add(subdomain.lower())

                logger.debug(
                    f'{self.source} 获取到 {len(results)} 个子域名，'
                    f'有效 {len(self.subdomains)} 个'
                )
            else:
                status_msg = data.get('status_message', 'Unknown')
                logger.debug(f'{self.source} 查询失败: {status_msg}')

        except Exception as e:
            logger.error(f'{self.source} 解析响应失败: {e}')
            self.subdomains = self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        执行 ThreatMiner 子域名查询

        :return: 发现的子域名集合
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
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = ThreatMiner(domain, config)
    return module.run()
