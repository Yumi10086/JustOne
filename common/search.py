"""
搜索引擎模块基类
继承 Module，增加搜索引擎专用方法
"""

import re
import time
import random
from typing import Set, List

from common.module import Module


class Search(Module):
    """搜索引擎基类"""

    def __init__(self, domain: str = '', config: dict = None):
        super().__init__(domain, config)
        self.delay = self.config.get('search_delay', 1.0)
        self.recursive = self.config.get('search_recursive', False)
        self._last_request_ts = 0.0

    def _throttle(self):
        """
        请求节流：同一模块两次请求之间至少间隔 delay 秒（附加随机抖动）

        搜索引擎为 HTML 页面抓取，请求过密容易触发验证码或封禁 IP。
        官方 API 类模块（datasets/certificates 等）不继承本类，不受影响。
        """
        if self.delay and self.delay > 0:
            elapsed = time.time() - self._last_request_ts
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed + random.uniform(0, self.delay * 0.3))
        self._last_request_ts = time.time()

    def get(self, url, params=None, check=True, ignore=False, raise_error=False, **kwargs):
        """
        发送带节流的 GET 请求

        :param str url: 请求 URL
        :param dict params: 请求参数
        :param bool check: 是否检查响应
        :param bool ignore: 是否忽略错误（降低日志级别）
        :param bool raise_error: 是否抛出错误
        :param kwargs: 其他参数
        :return: 响应对象
        """
        self._throttle()
        return super().get(url, params=params, check=check, ignore=ignore,
                           raise_error=raise_error, **kwargs)

    def post(self, url, data=None, check=True, **kwargs):
        """
        发送带节流的 POST 请求

        :param str url: 请求 URL
        :param dict data: 请求数据
        :param bool check: 是否检查响应
        :param kwargs: 其他参数
        :return: 响应对象
        """
        self._throttle()
        return super().post(url, data=data, check=check, **kwargs)

    def check_subdomains(self, subdomains: Set[str]) -> bool:
        """
        检查是否继续搜索分页

        :param set subdomains: 当前页发现的子域名
        :return: True 继续分页，False 停止
        """
        if not subdomains:
            return False
        return True

    def filter(self, domain: str, subdomains: Set[str]) -> List[str]:
        """
        分析子域名，筛选出现次数过多的子域前缀以便排除后重新搜索

        :param str domain: 主域名
        :param set subdomains: 已发现的子域名集合
        :return: 需要排除的子域名前缀列表
        """
        statements = set()
        subdomains_temp = set()
        for subdomain in subdomains:
            subdomain_temp = subdomain.replace('.' + domain, '')
            result = re.search(r'([a-zA-Z0-9])', subdomain_temp)
            if not result:
                continue
            subdomain_temp = subdomain_temp[:result.end()]
            subdomains_temp.add(subdomain_temp)
        for subdomain_temp in subdomains_temp:
            count = sum(1 for s in subdomains if subdomain_temp in s)
            if count >= 100:
                statements.add(subdomain_temp)
        return list(statements)

    def recursive_subdomain(self) -> Set[str]:
        """
        返回已发现的子域名（用于递归搜索）

        :return: 子域名集合
        """
        return self.subdomains.copy()
