"""
DNS 解析验证模块
"""

from typing import Optional, Dict, Any, Set, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from common.module import Module
from common import resolve
from common import utils
from config.logging import logger


class DNSCheck(Module):
    """
    DNS 解析验证模块

    验证子域名是否可以正常解析。
    支持通过 ThreadPoolExecutor 并发解析，大幅提升批量检查速度。
    """

    def __init__(self, domain: str, config: Optional[dict] = None, concurrent: int = 200):
        """
        初始化 DNS 检查模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        :param int concurrent: DNS 解析并发数，默认 200
        """
        super().__init__(domain, config)
        self.module = 'DNSCheck'
        self.source = 'dns_check'
        self.concurrent = concurrent

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
            logger.debug(f'{subdomain} DNS 解析失败: {e}')
        return None

    def run(self, subdomains: Optional[Set[str]] = None, show_progress: bool = True) -> list:
        """
        执行 DNS 解析验证（并发版本）

        使用 ThreadPoolExecutor 并发解析，大幅提升批量检查速度。
        并发数可通过 __init__ 的 concurrent 参数配置，默认 200。

        :param Set[str] subdomains: 要检查的子域名集合
        :param bool show_progress: 是否显示进度条
        :return: 可解析的子域名列表
        """
        target_subdomains = subdomains or self.subdomains

        if not target_subdomains:
            return []

        self.subdomains = target_subdomains
        self.begin()

        candidates = list(target_subdomains)
        total = len(candidates)
        resolved_list: List[Dict[str, Any]] = []

        if show_progress:
            pbar = tqdm(
                total=total,
                desc='DNS 解析',
                ncols=60,
                mininterval=0.3,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )

        workers = min(self.concurrent, total) if total > 0 else 1

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self.check, s): s for s in candidates}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    resolved_list.append(result)
                    self.infos[result['subdomain']] = result
                if show_progress:
                    pbar.update(1)

        if show_progress:
            pbar.close()

        self.subdomains = set(r['subdomain'] for r in resolved_list)
        self.finish()

        logger.info(
            f'DNS 解析完成: {len(resolved_list)}/{total} 可解析，'
            f'并发数 {workers}，耗时 {self.elapse:.1f}s'
        )

        return resolved_list
