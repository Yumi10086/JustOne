"""
AlienVault OTX 威胁情报模块
"""

import time
from typing import Optional, Set

from common.module import Module
from config.logging import logger


class AlienVaultOTX(Module):
    """
    AlienVault OTX 被动 DNS 子域名搜集模块

    通过 OTX 被动 DNS API 获取目标域名的历史解析记录，
    从中提取子域名信息。无需认证即可使用，但建议配置 API Key 以获得更高配额。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 AlienVaultOTX 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典，支持 alienvault_api_key
        """
        super().__init__(domain, config)
        self.module = 'AlienVaultOTX'
        self.source = 'alienvault'
        self.addr = f'https://otx.alienvault.com/api/v1/indicators/domain/{self.domain}/passive_dns'

        self.api_key = ''
        if config and isinstance(config, dict):
            self.api_key = config.get('alienvault_api_key', '')
        self.min_interval = 2   # OTX 免费版速率限制严格

    def query(self):
        """
        查询 OTX 被动 DNS 并提取子域名
        """
        logger.debug(f'{self.source} 等待 {self.min_interval}s 以避免速率限制...')
        time.sleep(self.min_interval)

        self.header = self.get_header()
        self.proxy = self.get_proxy(self.source)

        if self.api_key:
            self.header['X-OTX-API-KEY'] = self.api_key

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
            passive_dns = data.get('passive_dns', [])

            for record in passive_dns:
                hostname = record.get('hostname', '')
                if hostname and hostname.endswith(self.domain):
                    self.subdomains.add(hostname)

            logger.debug(
                f'{self.source} 获取到 {len(passive_dns)} 条被动 DNS 记录，'
                f'提取 {len(self.subdomains)} 个有效子域名'
            )

        except Exception as e:
            logger.error(f'{self.source} 解析响应失败: {e}')
            self.subdomains = self.collect_subdomains(resp)

    def run(self) -> Set[str]:
        """
        执行 AlienVault OTX 子域名查询

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
    module = AlienVaultOTX(domain, config)
    return module.run()
