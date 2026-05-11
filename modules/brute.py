"""
子域爆破模块
"""

import time
import asyncio
from pathlib import Path
from typing import Optional, Set, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from config.logging import logger
from common import resolve
from common.domain import Domain


brute_config = {
    'enabled': True,
    'concurrent': 2000,
    'wordlist': None,
    'recursive': False,
    'recursive_depth': 2,
    'wildcard_check': True,
    'wildcard_deal': True,
}


def set_brute_config(config: dict):
    """设置爆破模块全局配置"""
    brute_config.update(config)


class Brute:
    """
    子域暴力猜测模块

    使用字典生成候选子域名并进行 DNS 解析验证
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化爆破模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        self.domain = domain
        self.config = config or {}

        self.concurrent = self.config.get('concurrent', brute_config.get('concurrent', 2000))
        self.wordlist = self.config.get('wordlist', brute_config.get('wordlist'))
        self.recursive = self.config.get('recursive', brute_config.get('recursive', False))
        self.recursive_depth = self.config.get('recursive_depth', brute_config.get('recursive_depth', 2))
        self.wildcard_check = self.config.get('wildcard_check', brute_config.get('wildcard_check', True))
        self.wildcard_deal = self.config.get('wildcard_deal', brute_config.get('wildcard_deal', True))

        domain_obj = Domain(domain)
        self.registered_domain = domain_obj.registered()

        self.subdomains: Set[str] = set()
        self.wordlist_lines: List[str] = []
        self._wildcard_ips: Set[str] = set()

        self.start_time = time.time()
        self.end_time = None
        self.elapse = None

    def load_wordlist(self) -> bool:
        """
        加载爆破字典

        :return: 是否加载成功
        """
        if self.wordlist is None:
            project_root = Path(__file__).parent.parent
            default_wordlist = project_root / 'data' / 'subnames.txt'
            if default_wordlist.exists():
                self.wordlist = default_wordlist
            else:
                logger.warning(f'未找到默认爆破字典: {default_wordlist}')
                return False

        wordlist_path = Path(self.wordlist)
        if not wordlist_path.exists():
            logger.error(f'爆破字典文件不存在: {wordlist_path}')
            return False

        try:
            with open(wordlist_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.wordlist_lines = [line.strip() for line in f if line.strip()]
            logger.info(f'加载爆破字典成功，共 {len(self.wordlist_lines)} 个条目')
            return True
        except Exception as e:
            logger.error(f'加载爆破字典失败: {e}')
            return False

    def check_wildcard(self, prefix: str = '_check_wildcard_') -> bool:
        """
        检查泛解析

        :param str prefix: 检测用的前缀
        :return: 是否存在泛解析
        """
        if not self.wildcard_check:
            return False

        test_domain = f'{prefix}.{self.domain}'
        try:
            info = resolve.resolve_domain(test_domain)
            if info and info.get('ip'):
                self._wildcard_ips.add(info['ip'])
                logger.warning(f'检测到泛解析，IP: {info["ip"]}')
                return True
        except Exception:
            pass
        return False

    def generate_candidates(self, wordlist: List[str] = None) -> List[str]:
        """
        生成候选子域名

        :param List[str] wordlist: 字典列表，默认使用内置字典
        :return: 候选子域名列表
        """
        if wordlist is not None and len(wordlist) > 0:
            words = wordlist
        else:
            words = self.wordlist_lines

        seen = set()
        candidates = []

        for word in words:
            if not word:
                continue
            candidate = f'{word}.{self.domain}'
            if candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)

        logger.debug(f'生成 {len(candidates)} 个候选子域名')
        return candidates

    def resolve_batch(self, candidates: List[str], show_progress: bool = True) -> Set[str]:
        """
        批量解析候选子域名

        :param List[str] candidates: 候选子域名列表
        :param bool show_progress: 是否显示进度条
        :return: 有效子域名集合
        """
        results = set()
        total = len(candidates)
        if total == 0:
            return results

        def resolve_one(candidate: str) -> Optional[str]:
            try:
                info = resolve.resolve_domain(candidate)
                if info and info.get('ip'):
                    if self.wildcard_deal and self._wildcard_ips:
                        if info['ip'] in self._wildcard_ips:
                            return None
                    return candidate
            except Exception:
                pass
            return None

        pbar = None
        last_update_percent = -1

        if show_progress:
            pbar = tqdm(
                total=total,
                desc='爆破进度',
                ncols=60,
                mininterval=0.5,
                position=0,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )

        if self.concurrent > 1 and total > 1:
            with ThreadPoolExecutor(max_workers=min(self.concurrent, total)) as executor:
                futures = {executor.submit(resolve_one, cand): cand for cand in candidates}
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        results.add(result)
                    if show_progress and pbar:
                        pbar.update(1)
                        current_percent = int(pbar.n * 100 / total)
                        if current_percent - last_update_percent >= 5:
                            pbar.refresh()
                            last_update_percent = current_percent
        else:
            for candidate in candidates:
                result = resolve_one(candidate)
                if result:
                    results.add(result)
                if show_progress and pbar:
                    pbar.update(1)
                    current_percent = int(pbar.n * 100 / total)
                    if current_percent - last_update_percent >= 5:
                        pbar.refresh()
                        last_update_percent = current_percent

        if show_progress and pbar:
            pbar.close()

        return results

    def run(self, wordlist: Optional[List[str]] = None, show_progress: bool = True) -> Set[str]:
        """
        执行爆破

        :param List[str] wordlist: 可选的字典列表
        :param bool show_progress: 是否显示进度条
        :return: 发现的子域名集合
        """
        logger.info(f'开始爆破子域名: {self.domain}')
        self.start_time = time.time()

        if not self.load_wordlist():
            return set()

        if self.check_wildcard():
            logger.info(f'检测到泛解析，将跳过相同 IP 的结果')

        self.subdomains = self._run_recursive(wordlist, 1, show_progress)

        self.end_time = time.time()
        self.elapse = round(self.end_time - self.start_time, 1)
        logger.info(f'爆破完成，发现 {len(self.subdomains)} 个子域名，耗时 {self.elapse} 秒')

        return self.subdomains

    def _run_recursive(self, wordlist: Optional[List[str]], depth: int, show_progress: bool) -> Set[str]:
        """
        递归执行爆破

        :param List[str] wordlist: 字典列表
        :param int depth: 当前递归深度
        :param bool show_progress: 是否显示进度条
        :return: 发现的子域名集合
        """
        results = set()

        if wordlist is not None and len(wordlist) > 0:
            words = wordlist
        else:
            words = self.wordlist_lines

        candidates = self.generate_candidates(words)
        logger.info(f'第 {depth} 层: 开始解析 {len(candidates)} 个候选子域名')

        batch_results = self.resolve_batch(candidates, show_progress)
        results.update(batch_results)

        if self.recursive and depth < self.recursive_depth:
            logger.info(f'第 {depth} 层: 发现 {len(batch_results)} 个子域名，继续递归...')
            for subdomain in batch_results:
                try:
                    subdomain_obj = Domain(subdomain)
                    base_domain = subdomain_obj.registered()
                    if base_domain != self.domain:
                        logger.debug(f'跳过跨域: {subdomain} -> {base_domain}')
                        continue

                    subdomain_prefix = subdomain.replace(f'.{self.domain}', '')
                    new_depth = depth + 1
                    logger.info(f'递归爆破: {subdomain} (第 {new_depth} 层)')
                    sub_brute = Brute(
                        self.domain,
                        {
                            'concurrent': self.concurrent,
                            'recursive': True,
                            'recursive_depth': self.recursive_depth,
                            'wildcard_check': False,
                            'wildcard_deal': False,
                        }
                    )
                    sub_results = sub_brute._run_recursive(
                        [subdomain_prefix], new_depth, show_progress
                    )
                    results.update(sub_results)
                except Exception as e:
                    logger.debug(f'递归爆破 {subdomain} 失败: {e}')

        return results

    def get_elapse(self) -> Optional[float]:
        """
        获取执行耗时

        :return: 执行耗时（秒）
        """
        return self.elapse