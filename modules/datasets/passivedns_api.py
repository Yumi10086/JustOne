"""
Mnemonic PassiveDNS API 子域查询模块
"""

from typing import Optional, Set

from common.module import Module
from config.logging import logger


class PassiveDnsAPI(Module):
    """
    Mnemonic PassiveDNS API v3 子域查询接口

    由挪威 CERT (Mnemonic) 运营的被动 DNS 服务。
    公开查询无需认证，免费限额 1000 请求/天。

    API 端点: https://api.mnemonic.no/pdns/v3/{domain}
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 PassiveDNS API 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'PassiveDnsAPI'
        self.source = 'api.mnemonic.no'
        self.api_url = 'https://api.mnemonic.no/pdns/v3/'

    def query(self):
        """
        向 Mnemonic API 查询子域

        分页逻辑：
        1. 查询 api.mnemonic.no/pdns/v3/{domain}?limit=1000
        2. 从响应 data[].query 中提取匹配目标域名的子域
        3. 若 count > limit，递增 offset 继续分页
        """
        self.header = self.get_header()
        self.header.update({'User-Agent': 'JustOne/1.0'})
        self.proxy = self.get_proxy(self.source)

        limit = 500
        offset = 0

        while True:
            url = f'{self.api_url}{self.domain}?limit={limit}&offset={offset}'
            resp = self.get(url, check=False)
            if not resp:
                logger.error(f'{self.source} 模块请求失败')
                return

            if resp.status_code != 200:
                logger.warning(
                    f'{self.source} 返回状态码 {resp.status_code}'
                )
                return

            try:
                data = resp.json()
            except Exception as e:
                logger.error(f'{self.source} JSON 解析失败: {e}')
                return

            if data.get('responseCode') != 200:
                logger.warning(
                    f'{self.source} API 返回错误: {data.get("messages", [])}'
                )
                return

            records = data.get('data', [])
            if not records:
                break

            # 从每个记录的 query 字段提取匹配目标域名的子域
            for record in records:
                query_name = record.get('query', '')
                if self._is_subdomain(query_name):
                    self.subdomains.add(query_name)

            # 检查是否还有更多页
            total = data.get('count', 0)
            returned = len(records)
            offset += returned
            if offset >= total:
                break

    def _is_subdomain(self, name: str) -> bool:
        """
        判断域名是否是目标域名的子域

        :param name: 待检查的域名
        :return: 是否为子域名
        """
        if not name:
            return False
        domain_lower = self.domain.lower()
        name_lower = name.lower()
        return name_lower == domain_lower or name_lower.endswith('.' + domain_lower)

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
    module = PassiveDnsAPI(domain, config)
    return module.run()
