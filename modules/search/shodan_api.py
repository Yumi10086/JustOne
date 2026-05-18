"""
Shodan API 搜索模块
使用官方 shodan 库
"""

from typing import Optional, Set

import shodan

from common.search import Search
from config import settings
from config.logging import logger


class ShodanAPI(Search):
    """
    Shodan API 子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'ShodanAPI'
        self.source = 'shodan.io'
        self.key = settings.shodan_api_key

    def _get_api(self) -> Optional[shodan.Shodan]:
        """
        获取 Shodan API 对象

        :return: Shodan API 对象
        """
        self.proxy = self.get_proxy(self.source)
        return shodan.Shodan(self.key, proxies=self.proxy)

    def _search_dns(self, api: shodan.Shodan):
        """
        通过 DNS 域名接口获取子域名

        :param api: Shodan API 对象
        """
        try:
            info = api.dns.domain_info(self.domain)
        except shodan.APIError as e:
            logger.warning(f'{self.source} DNS 查询失败: {e}')
            return
        except Exception as e:
            logger.error(f'{self.source} DNS 查询异常: {e}')
            return

        records = info.get('data', [])
        if not records:
            logger.info(f'{self.source} DNS 未发现子域名记录')
            return

        for record in records:
            sub = record.get('subdomain', '').lower()
            if sub and sub != self.domain:
                subdomain = f'{sub}.{self.domain}'.lower()
                self.subdomains.add(subdomain)
        logger.info(f'{self.source} DNS 发现 {len(self.subdomains)} 个子域名')

    def _search_hostname(self, api: shodan.Shodan):
        """
        通过 hostname 搜索接口获取子域名

        :param api: Shodan API 对象
        """
        page = 1
        while True:
            try:
                results = api.search(f'hostname:.{self.domain}', page=page)
            except shodan.APIError as e:
                logger.warning(f'{self.source} hostname 搜索失败: {e}')
                break
            except Exception as e:
                logger.error(f'{self.source} hostname 搜索异常: {e}')
                break

            matches = results.get('matches', [])
            if not matches:
                break

            for banner in matches:
                hostnames = banner.get('hostnames', [])
                for host in hostnames:
                    host = host.lower()
                    if self.domain in host:
                        self.subdomains.add(host)

            if page >= 10:
                break
            page += 1

        logger.info(f'{self.source} hostname 搜索总计 {len(self.subdomains)} 个子域名')

    def run(self) -> Set[str]:
        """执行 Shodan 搜索"""
        if not self.have_api(self.key):
            return self.subdomains
        self.begin()
        api = self._get_api()
        if not api:
            logger.warning(f'{self.source} 初始化 API 失败')
            self.finish()
            return self.subdomains

        self._search_dns(api)
        self._search_hostname(api)

        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = ShodanAPI(domain, config)
    return module.run()
