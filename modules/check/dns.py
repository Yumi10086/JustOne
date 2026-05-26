"""
DNS 解析验证模块
"""

from typing import Optional, Dict, Any, Set

from tqdm import tqdm

from common.module import Module
from common import resolve
from common import utils


class DNSCheck(Module):
    """
    DNS 解析验证模块

    验证子域名是否可以正常解析
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 DNS 检查模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'DNSCheck'
        self.source = 'dns_check'

    def check(self, subdomain: str) -> Optional[Dict[str, Any]]:
        """
        检查单个子域名的 DNS 解析

        :param str subdomain: 子域名
        :return: 解析结果字典，解析失败返回 None
        """
        try:
            info = resolve.resolve_domain(subdomain)
            if info and info.get('ip'):
                return {
                    'subdomain': subdomain,
                    'ip': info['ip'],
                    'resolve': True,
                }
        except Exception as e:
            logger = utils.get_logger()
            logger.debug(f'{subdomain} DNS 解析失败: {e}')
        return None

    def run(self, subdomains: Optional[Set[str]] = None, show_progress: bool = True) -> list:
        """
        执行 DNS 解析验证

        :param Set[str] subdomains: 要检查的子域名集合
        :param bool show_progress: 是否显示进度条
        :return: 可解析的子域名列表
        """
        target_subdomains = subdomains or self.subdomains

        if not target_subdomains:
            return []

        self.subdomains = target_subdomains
        self.begin()

        resolved_list = []
        if show_progress:
            pbar = tqdm(
                total=len(target_subdomains),
                desc='DNS 解析',
                ncols=60,
                mininterval=0.3,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )
        for subdomain in target_subdomains:
            result = self.check(subdomain)
            if result:
                resolved_list.append(result)
                self.infos[subdomain] = result
            if show_progress:
                pbar.update(1)
        if show_progress:
            pbar.close()

        self.subdomains = set(r['subdomain'] for r in resolved_list)
        self.finish()
        return resolved_list