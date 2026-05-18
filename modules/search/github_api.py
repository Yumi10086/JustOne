"""
GitHub API 搜索模块
"""

import time
from typing import Optional, Set

from common.search import Search
from config import settings
from config.logging import logger


class GithubAPI(Search):
    """
    GitHub API 子域收集模块
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'GithubAPI'
        self.source = 'github.com'
        self.addr = 'https://api.github.com/search/code'
        self.delay = 5
        self.token = settings.github_token

    def search(self):
        """向接口查询子域并做子域匹配"""
        self.get_header()
        self.proxy = self.get_proxy(self.source)
        self.header.update(
            {'Accept': 'application/vnd.github.v3.text-match+json'})
        self.header.update(
            {'Authorization': 'token ' + self.token})

        page = 1
        while True:
            time.sleep(self.delay)
            params = {'q': self.domain, 'per_page': 100,
                      'page': page, 'sort': 'indexed'}
            try:
                resp = self.get(self.addr, params=params)
            except Exception as e:
                logger.error(f'GitHub API 请求异常: {e}')
                break
            if not resp or resp.status_code != 200:
                logger.error(f'{self.source} 模块查询失败')
                break
            subdomains = self.match_subdomains(resp)
            if not subdomains:
                break
            self.subdomains.update(subdomains)
            page += 1
            try:
                resp_json = resp.json()
            except Exception as e:
                logger.error(f'GitHub API 响应解析失败: {e}')
                break
            total_count = resp_json.get('total_count')
            if not isinstance(total_count, int):
                break
            if page * 100 > total_count:
                break
            if page * 100 > 1000:
                break

    def run(self) -> Set[str]:
        """执行 GitHub 搜索"""
        if not self.have_api(self.token):
            return self.subdomains
        self.begin()
        self.search()
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = GithubAPI(domain, config)
    return module.run()
