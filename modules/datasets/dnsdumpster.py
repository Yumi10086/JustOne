"""
DNSDumpster REST API 子域名查询模块
"""

from typing import Optional, Set

from common.module import Module
from config.settings import settings
from config.logging import logger


class DNSDumpster(Module):
    """
    DNSDumpster 子域名查询模块

    通过 DNSDumpster REST API 获取目标域名的 DNS 记录信息。
    需要在 config/.env 中配置 DNSDUMPSTER_API_KEY。
    免费账户限制 50 条记录，Plus 账户 200 条。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 DNSDumpster 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'DNSDumpster'
        self.source = 'dnsdumpster'
        self.api_key = settings.dnsdumpster_api_key
        self.delay = 3

    def query(self):
        """
        调用 DNSDumpster REST API 查询 DNS 记录并提取子域名
        """
        self.header = self.get_header()
        self.header['X-API-Key'] = self.api_key
        self.proxy = self.get_proxy(self.source)
        url = f'https://api.dnsdumpster.com/domain/{self.domain}'
        resp = self.get(url, check=False)

        if not resp:
            return

        if resp.status_code == 401:
            logger.warning(f'{self.source} API Key 无效或已过期 (401)')
            return
        if resp.status_code == 429:
            logger.warning(f'{self.source} 请求频率过高 (429)，速率限制：1 请求 / 2 秒')
            return
        if resp.status_code != 200:
            try:
                err = resp.json()
                logger.warning(f'{self.source} API 错误 ({resp.status_code}): {err.get("error", "")}')
            except Exception:
                logger.warning(f'{self.source} 返回错误状态码: {resp.status_code}')
            return

        try:
            data = resp.json()
        except Exception:
            logger.warning(f'{self.source} 响应 JSON 解析失败')
            return

        hosts = set()
        for record_type in ('a', 'cname', 'ns', 'mx'):
            records = data.get(record_type, [])
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
                        host = record.get('host', '')
                        if host and self.domain in host:
                            hosts.add(host.lower())

        subdomains = self.match_subdomains(str(data))
        hosts.update(subdomains)
        self.subdomains = hosts

        a_count = data.get('total_a_recs', 0)
        if a_count:
            logger.info(f'{self.source} 查询完成，发现 {len(self.subdomains)} 个子域名（共 {a_count} 条 A 记录）')
        else:
            logger.info(f'{self.source} 查询完成，发现 {len(self.subdomains)} 个子域名')

    def run(self) -> Set[str]:
        """
        执行 DNSDumpster 子域名查询

        :return: 发现的子域名集合
        """
        if not self.have_api(self.api_key):
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
    module = DNSDumpster(domain, config)
    return module.run()
