"""
ZoomEye API v2 搜索模块
"""

import base64
import time
from typing import Optional, Set

from common.search import Search
from config import settings
from config.logging import logger


class ZoomEyeAPI(Search):
    """
    ZoomEye API v2 子域收集模块

    通过 ZoomEye v2 API 搜索域名关联的资产信息，提取子域名。
    在 config/.env 中配置 ZOOMEYE_API。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 ZoomEye API 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'ZoomEyeAPI'
        self.source = 'zoomeye.org'
        self.addr = 'https://api.zoomeye.org/v2/search'
        self.delay = 2
        self.api_key = settings.zoomeye_api
        self.pagesize = 10000

    def search(self):
        """
        发送 ZoomEye v2 搜索请求并提取域名信息
        """
        page_num = 1
        query = f'hostname:"{self.domain}"'
        qbase64 = base64.b64encode(query.encode()).decode()

        while True:
            time.sleep(self.delay)
            self.header = self.get_header()
            self.header['API-KEY'] = self.api_key
            self.proxy = self.get_proxy(self.source)

            body = {
                'qbase64': qbase64,
                'page': page_num,
                'pagesize': self.pagesize,
                'fields': 'domain,ip,port',
            }
            resp = self.post(self.addr, json=body)
            if not resp:
                return

            if resp.status_code == 401:
                logger.warning(f'{self.source} API-KEY 无效或已过期 (401)')
                return
            if resp.status_code == 402:
                logger.warning(f'{self.source} 账户额度不足 (402)，请升级套餐或等待额度重置')
                return
            if resp.status_code == 403:
                logger.warning(f'{self.source} 无权限访问，请检查 API-KEY 权限 (403)')
                return
            if resp.status_code == 422:
                try:
                    err = resp.json()
                    logger.warning(f'{self.source} 请求参数错误 (422): {err.get("message", "")}')
                except Exception:
                    logger.warning(f'{self.source} 请求参数错误 (422)')
                return
            if resp.status_code == 429:
                logger.warning(f'{self.source} 请求频率过高 (429)，等待后重试')
                time.sleep(10)
                continue
            if resp.status_code != 200:
                try:
                    err = resp.json()
                    logger.warning(f'{self.source} API 错误 ({resp.status_code}): {err.get("message", err.get("error", ""))}')
                except Exception:
                    logger.error(f'{self.source} 返回错误状态码: {resp.status_code}')
                return

            try:
                result = resp.json()
                code = result.get('code')
                if code != 60000:
                    message = result.get('message', '未知错误')
                    logger.warning(f'{self.source} API 响应错误 (code={code}): {message}')
                    return

                if 'total' in result:
                    logger.info(f'{self.source} 共匹配 {result["total"]} 条记录')

                data = result.get('data', [])
                for item in data:
                    domain = item.get('domain', '')
                    if domain and self.domain in domain:
                        self.subdomains.add(domain.lower())

                if len(data) < self.pagesize:
                    break

                page_num += 1
                if page_num > 500:
                    break
            except Exception as e:
                logger.error(f'{self.source} 解析响应失败: {e}')
                return

    def run(self) -> Set[str]:
        """
        执行 ZoomEye v2 搜索

        :return: 发现的子域名集合
        """
        if not self.have_api(self.api_key):
            return self.subdomains
        self.begin()
        self.search()
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
    module = ZoomEyeAPI(domain, config)
    return module.run()
