"""
Cloudflare API 子域名查询模块

通过 Cloudflare API v4 查询目标域名的 DNS 记录信息，从中提取子域名。
若域名已在 Cloudflare 中管理则直接查询；
若未管理则临时创建 Zone 触发 DNS 扫描后清理。
使用 API Token + Bearer 认证，在 config/.env 中配置 CLOUDFLARE_API_TOKEN。
"""

from time import sleep
from typing import Optional, Set

from common.module import Module
from config.settings import settings
from config.logging import logger


class CloudFlareAPI(Module):
    """
    Cloudflare API 子域名查询模块

    通过 Cloudflare API v4 查询目标域名的 DNS 记录，提取子域名。
    需要配置 CLOUDFLARE_API_TOKEN，Token 需具有 Zone:Read、DNS:Read
    以及 Zone:Edit 权限（临时创建 Zone 需要）。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 CloudFlareAPI 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'CloudFlareAPI'
        self.source = 'cloudflare_api'
        self.api_token = settings.cloudflare_api_token
        self.base_url = 'https://api.cloudflare.com/client/v4'
        self.zone_id = None

    def _set_auth_header(self):
        """
        设置 Authorization 请求头
        """
        self.header = self.get_header()
        self.header['Authorization'] = f'Bearer {self.api_token}'
        self.header['Content-Type'] = 'application/json'

    def get_account_id(self) -> Optional[str]:
        """
        获取账户 ID

        通过 accounts 列表获取第一个账户 ID。

        :return: 账户 ID，若获取失败则返回 None
        """
        self._set_auth_header()
        self.proxy = self.get_proxy(self.source)

        resp = self.get(f'{self.base_url}/accounts')
        if not resp:
            logger.debug(f'{self.source} 获取账户列表失败: 无响应')
            return None

        if resp.status_code != 200:
            logger.debug(f'{self.source} 获取账户列表失败 ({resp.status_code})')
            return None

        accounts = resp.json().get('result', [])
        if not accounts:
            logger.warning(f'{self.source} 未找到关联账户，请检查 CLOUDFLARE_API_TOKEN 权限')
            return None

        account_id = accounts[0].get('id', '')
        logger.debug(f'{self.source} 获取到账户 ID: {account_id}')
        return account_id

    def get_or_create_zone(self, account_id: str) -> Optional[str]:
        """
        获取已有 Zone 或创建临时 Zone

        先查询域名是否已在 Cloudflare 中管理，若不存在则创建临时 Zone
        并通过 jump_start 触发 Cloudflare 自动 DNS 扫描。

        :param str account_id: 账户 ID
        :return: Zone ID，若失败则返回 None
        """
        self._set_auth_header()
        self.proxy = self.get_proxy(self.source)

        resp = self.get(f'{self.base_url}/zones',
                        params={'name': self.domain}, check=False)

        if not resp:
            return None

        if resp.status_code == 403:
            logger.debug(f'{self.source} {self.domain} 无权访问或被禁止 (403)')
            return None

        if resp.status_code != 200:
            logger.debug(f'{self.source} 查询 Zone 失败 ({resp.status_code}): {resp.text[:200]}')
            return None

        data = resp.json()
        if not data.get('success'):
            errors = data.get('errors', [])
            for err in errors:
                logger.debug(f'{self.source} API 错误: {err.get("message", "")}')
            return None

        zones = data.get('result', [])
        if zones:
            zone_id = zones[0].get('id', '')
            logger.debug(f'{self.source} 找到已有 Zone: {self.domain} (id={zone_id})')
            return zone_id

        return self.create_zone(account_id)

    def create_zone(self, account_id: str) -> Optional[str]:
        """
        创建临时 Zone 触发 Cloudflare DNS 扫描

        :param str account_id: 账户 ID
        :return: Zone ID，若创建失败则返回 None
        """
        body = {
            'name': self.domain,
            'account': {'id': account_id},
            'jump_start': True,
            'type': 'full',
        }
        resp = self.post(f'{self.base_url}/zones', json=body, check=False)

        if not resp:
            logger.debug(f'{self.source} 创建 Zone 失败: 无响应')
            return None

        if resp.json().get('success'):
            zone_id = resp.json()['result']['id']
            self.zone_id = zone_id
            logger.info(f'{self.source} 已创建临时 Zone 触发 DNS 扫描 (id={zone_id})')
            return zone_id

        logger.debug(f'{self.source} 创建 Zone 失败: {resp.text[:200]}')
        return None

    def list_dns(self, zone_id: str):
        """
        分页获取 DNS 记录并提取子域名

        若 Zone 是新创建的，Cloudflare 需要时间完成自动 DNS 扫描，
        最多等待 6 次（每次 5 秒），找到记录后立即退出循环。

        :param str zone_id: Cloudflare Zone ID
        """
        per_page = 100
        max_wait_attempts = 6

        for attempt in range(max_wait_attempts):
            page = 1
            found_any = False

            while True:
                self._set_auth_header()
                self.proxy = self.get_proxy(self.source)

                dns_url = f'{self.base_url}/zones/{zone_id}/dns_records'
                resp = self.get(dns_url, params={'page': page, 'per_page': per_page},
                                check=False)

                if not resp:
                    logger.debug(f'{self.source} DNS 记录查询失败: 无响应')
                    return

                if resp.status_code != 200:
                    logger.debug(f'{self.source} DNS 记录查询失败 ({resp.status_code}): {resp.text[:200]}')
                    return

                data = resp.json()
                if not data.get('success'):
                    return

                result_info = data.get('result_info', {})
                total_pages = result_info.get('total_pages', 0)
                records = data.get('result', [])

                if records:
                    found_any = True
                    for record in records:
                        name = record.get('name', '')
                        if name:
                            subdomains = self.match_subdomains(name, distinct=True, fuzzy=True)
                            self.subdomains.update(subdomains)

                        content = record.get('content', '')
                        if content:
                            subdomains = self.match_subdomains(content, distinct=True, fuzzy=True)
                            self.subdomains.update(subdomains)

                    logger.debug(f'{self.source} DNS 第 {page}/{total_pages} 页，'
                                 f'共 {result_info.get("total_count", 0)} 条记录')

                if page >= total_pages:
                    break
                page += 1

            if found_any or attempt == max_wait_attempts - 1:
                return

            logger.debug(f'{self.source} 等待 Cloudflare DNS 扫描完成 ({attempt + 1}/{max_wait_attempts})')
            sleep(5)

    def cleanup(self):
        """
        删除临时创建的 Zone

        仅清理本模块创建的临时 Zone，已有 Zone 不做任何操作。
        """
        if not self.zone_id:
            return

        delete_url = f'{self.base_url}/zones/{self.zone_id}'
        resp = self.delete(delete_url, check=False)
        if resp and resp.status_code == 200:
            logger.info(f'{self.source} 已清理临时 Zone (id={self.zone_id})')
        else:
            status = resp.status_code if resp else '无响应'
            logger.debug(f'{self.source} 清理临时 Zone 失败 ({status})')
        self.zone_id = None

    def run(self) -> Set[str]:
        """
        执行 Cloudflare API 子域名查询

        :return: 发现的子域名集合
        """
        if not self.have_api(self.api_token):
            return self.subdomains

        self.begin()

        logger.info(f'开始 Cloudflare API 查询: {self.domain}')

        try:
            account_id = self.get_account_id()
            if not account_id:
                return self.subdomains

            zone_id = self.get_or_create_zone(account_id)
            if zone_id:
                self.list_dns(zone_id)

            logger.info(f'Cloudflare API 查询完成，发现 {len(self.subdomains)} 个子域名')

        except Exception as e:
            logger.error(f'Cloudflare API 查询出错: {e}')
        finally:
            self.cleanup()
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
    module = CloudFlareAPI(domain, config)
    return module.run()
