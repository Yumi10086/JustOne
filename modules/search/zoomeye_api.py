"""
ZoomEye API 搜索模块
"""

import time
from typing import Optional, Set

from common.search import Search
from config import settings
from config.logging import logger


class ZoomEyeAPI(Search):
    """
    ZoomEye API 子域收集模块

    支持两种认证方式:
    - 新版: API-KEY header (settings.zoomeye_api)
    - 旧版: JWT 登录 (已弃用，保留兼容)
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'ZoomEyeAPI'
        self.source = 'zoomeye.org'
        self.addr = 'https://api.zoomeye.org/web/search'
        self.delay = 2
        self.user = settings.zoomeye_email
        self.pwd = settings.zoomeye_password
        self.api_key = settings.zoomeye_api

    def _get_auth_token(self) -> Optional[str]:
        """
        获取认证凭据

        :return: API-KEY 字符串或 JWT token，失败返回 None
        """
        if self.api_key:
            logger.debug(f'{self.source} 使用 API-KEY 认证')
            return self.api_key

        if self.user and self.pwd:
            logger.debug(f'{self.source} 尝试 JWT 登录...')
            return self._jwt_login()

        return None

    def _jwt_login(self) -> Optional[str]:
        """
        旧版 JWT 登录（已弃用，保留兼容）

        :return: JWT token 或 None
        """
        url = 'https://api.zoomeye.org/user/login'
        data = {'username': self.user, 'password': self.pwd}
        resp = self.post(url=url, json=data)
        if not resp:
            logger.warning(f'{self.source} JWT 登录请求失败')
            return None
        try:
            json_data = resp.json()
            if resp.status_code == 200:
                logger.debug(f'{self.source} JWT 登录成功')
                return json_data.get('access_token')
            if resp.status_code == 404:
                logger.warning(
                    f'{self.source} JWT 登录 API 已弃用。'
                    f'请在 config/.env 中设置 ZOOMEYE_API=你的APIKey，'
                    f'并将 ZOOMEYE_EMAIL 和 ZOOMEYE_PASSWORD 留空'
                )
                return None
            err_msg = json_data.get('message') or json_data.get('error', '')
            logger.warning(f'{self.source} JWT 登录失败: {err_msg}')
            return None
        except Exception:
            return None

    def search(self, auth_token: str):
        """发送搜索请求并提取 hostname 字段"""
        page_num = 1
        while True:
            time.sleep(self.delay)
            self.get_header()
            self.proxy = self.get_proxy(self.source)
            self.header['Accept'] = 'application/json'
            if self.api_key:
                self.header['API-KEY'] = auth_token
            else:
                self.header.update({'Authorization': 'JWT ' + auth_token})
            params = {'query': 'hostname:' + self.domain, 'page': page_num}
            resp = self.get(self.addr, params)
            if not resp:
                return
            if resp.status_code == 401:
                logger.warning(f'{self.source} 认证失败 (401)，凭据无效或已过期')
                return
            if resp.status_code == 403:
                logger.warning(f'{self.source} 访问被拒绝 (403)，本月配额可能已用尽')
                break
            if resp.status_code == 429:
                logger.warning(f'{self.source} 请求频率过高 (429)，延迟后重试')
                time.sleep(10)
                continue
            if resp.status_code != 200:
                logger.error(f'{self.source} 返回错误状态码: {resp.status_code}')
                break
            try:
                data = resp.json()
                matches = data.get('matches', [])
                for match in matches:
                    if isinstance(match, dict):
                        host = (match.get('site') or
                                match.get('hostname') or
                                match.get('headers', '')).lower()
                        if self.domain in host:
                            self.subdomains.add(host)
            except Exception as e:
                logger.error(f'{self.source} 解析响应失败: {e}')
                break
            if not matches:
                break
            page_num += 1
            if page_num > 500:
                break

    def run(self) -> Set[str]:
        """执行 ZoomEye 搜索"""
        if not self.have_api(self.api_key or self.user, self.pwd or self.api_key):
            if not self.api_key and not (self.user and self.pwd):
                logger.warning(f'{self.source} 未配置认证信息')
                return self.subdomains
            return self.subdomains
        self.begin()
        auth_token = self._get_auth_token()
        if not auth_token:
            logger.warning(f'{self.source} 获取认证凭据失败，跳过')
            self.finish()
            return self.subdomains
        self.search(auth_token)
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = ZoomEyeAPI(domain, config)
    return module.run()
