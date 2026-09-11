"""
子域爆破模块
"""

import time
import asyncio
import sys
from pathlib import Path
from typing import Optional, Set, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from config.logging import logger
from common import resolve
from common.domain import Domain
from common.wildcard import WildcardInfo, detect_wildcard


brute_config = {
    'enabled': True,
    'concurrent': 2000,
    'wordlist': None,
    'recursive': False,
    'recursive_depth': 2,
    # 递归扇出上限：每层最多对多少个子域名继续递归（0 表示不限制）
    'recursive_max_fanout': 10,
    # 递归候选总量预算：整个递归树的候选数上限，防止字典过大导致查询爆炸
    'recursive_max_candidates': 100000,
    'wildcard_check': True,
    'wildcard_deal': True,
    'wildcard_probes': 3,
    'wildcard_cidr': False,
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
        self.recursive_max_fanout = self.config.get(
            'recursive_max_fanout', brute_config.get('recursive_max_fanout', 10))
        self.recursive_max_candidates = self.config.get(
            'recursive_max_candidates', brute_config.get('recursive_max_candidates', 100000))
        self.wildcard_check = self.config.get('wildcard_check', brute_config.get('wildcard_check', True))
        self.wildcard_deal = self.config.get('wildcard_deal', brute_config.get('wildcard_deal', True))
        self.wildcard_probes = self.config.get('wildcard_probes', brute_config.get('wildcard_probes', 3))
        self.wildcard_cidr = self.config.get('wildcard_cidr', brute_config.get('wildcard_cidr', False))

        domain_obj = Domain(domain)
        self.registered_domain = domain_obj.registered()

        self.subdomains: Set[str] = set()
        self.wordlist_lines: List[str] = []
        self._wildcard_ips: Set[str] = set()
        self._wildcard_info: Optional[WildcardInfo] = None
        # 递归候选总量预算（列表可变，跨层共享同一引用）
        self._budget: List[int] = [self.recursive_max_candidates]

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

    def check_wildcard(self, prefix: str = None) -> bool:
        """
        检查泛解析（多随机标签探测）

        :param str prefix: 兼容保留参数，当前不使用
        :return: 是否存在泛解析
        """
        if not self.wildcard_check:
            return False

        try:
            info = detect_wildcard(self.domain, probes=self.wildcard_probes)
            if info.detected:
                self._wildcard_info = info
                self._wildcard_ips = set(info.ips)
                logger.warning(f'检测到泛解析，IP: {sorted(info.ips)}')
                return True
        except Exception as e:
            logger.debug(f'泛解析检测异常: {e}')
        return False

    def _merge_nested_wildcard(self, base: str) -> Optional[WildcardInfo]:
        """
        检测 base 上的嵌套泛解析，仅保留相对父级新增的证据

        若探测结果完全可由父级泛解析（如 *.example.com）解释，则不视为嵌套泛解析。

        :param str base: 当前递归基础域名（如 dev.example.com）
        :return: 合并后的泛解析结果，无新增证据返回 None
        """
        nested = detect_wildcard(base, probes=self.wildcard_probes)
        if not nested.detected:
            return None

        parent = self._wildcard_info
        if not parent:
            return nested

        new_ips = nested.ips - parent.ips
        new_ipv6 = nested.ipv6s - parent.ipv6s
        new_cnames = nested.cnames - parent.cnames
        if not (new_ips or new_ipv6 or new_cnames):
            return None

        extra = WildcardInfo(
            domain=base,
            detected=True,
            ips=new_ips,
            ipv6s=new_ipv6,
            cnames=new_cnames,
        )
        logger.warning(
            f'检测到嵌套泛解析: {base} — IP={sorted(new_ips)} CNAME={sorted(new_cnames)}'
        )
        return parent.merge(extra)

    def generate_candidates(self, wordlist: List[str] = None, base: str = None) -> List[str]:
        """
        生成候选子域名

        :param List[str] wordlist: 字典列表，默认使用内置字典
        :param str base: 基础域名，默认使用目标注册域名（递归时传当前层子域名）
        :return: 候选子域名列表
        """
        if wordlist is not None and len(wordlist) > 0:
            words = wordlist
        else:
            words = self.wordlist_lines

        target_base = base or self.domain
        seen = set()
        candidates = []

        for word in words:
            if not word:
                continue
            candidate = f'{word}.{target_base}'
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
                    if (self.wildcard_deal and self._wildcard_info
                            and self._wildcard_info.matches_record(info, include_cidr=self.wildcard_cidr)):
                        return None
                    return candidate
            except Exception as e:
                logger.debug(f'DNS 解析异常 {candidate}: {e}')
                pass
            return None

        last_update_percent = -1
        start_time = time.time()

        if show_progress:
            pbar = tqdm(
                total=total,
                desc='爆破进度',
                ncols=60,
                mininterval=0.5,
                position=0,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                leave=False,
            )
        else:
            pbar = None

        def update_progress(completed):
            nonlocal last_update_percent
            if not show_progress:
                return
            current_percent = int(completed * 100 / total)
            if current_percent - last_update_percent >= 1:
                if pbar is not None:
                    pbar.n = completed
                    pbar.refresh()
                last_update_percent = current_percent

        if self.concurrent > 1 and total > 1:
            with ThreadPoolExecutor(max_workers=min(self.concurrent, total)) as executor:
                futures = {executor.submit(resolve_one, cand): cand for cand in candidates}
                completed = 0
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        results.add(result)
                    completed += 1
                    update_progress(completed)
        else:
            completed = 0
            for candidate in candidates:
                result = resolve_one(candidate)
                if result:
                    results.add(result)
                completed += 1
                update_progress(completed)

        if show_progress and pbar is not None:
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

        if self.recursive:
            logger.warning(
                f'已启用递归爆破: 深度={self.recursive_depth}, '
                f'扇出上限={self.recursive_max_fanout}, '
                f'候选总量上限={self.recursive_max_candidates}，请注意 DNS 查询量'
            )
        # 重置候选预算（支持重复调用 run）
        self._budget = [self.recursive_max_candidates]

        self.subdomains = self._run_recursive(wordlist, 1, show_progress)

        self.end_time = time.time()
        self.elapse = round(self.end_time - self.start_time, 1)
        logger.info(f'爆破完成，发现 {len(self.subdomains)} 个子域名，耗时 {self.elapse} 秒')

        return self.subdomains

    def _run_recursive(self, wordlist: Optional[List[str]], depth: int,
                       show_progress: bool, base: str = None) -> Set[str]:
        """
        递归执行爆破

        :param List[str] wordlist: 字典列表
        :param int depth: 当前递归深度
        :param bool show_progress: 是否显示进度条
        :param str base: 当前层基础域名，默认使用目标注册域名
        :return: 发现的子域名集合
        """
        results = set()

        if wordlist is not None and len(wordlist) > 0:
            words = wordlist
        else:
            words = self.wordlist_lines

        target_base = base or self.domain

        # 递归候选总量预算：耗尽则停止，防止字典过大导致查询爆炸
        if self._budget[0] <= 0:
            logger.warning(
                f'递归爆破候选预算已耗尽（上限 {self.recursive_max_candidates}），停止递归'
            )
            return results

        candidates = self.generate_candidates(words, base=target_base)
        self._budget[0] -= len(candidates)
        if self._budget[0] < 0:
            logger.warning(
                f'递归爆破候选总量超过上限 {self.recursive_max_candidates}，将不再继续递归'
            )
        logger.info(f'第 {depth} 层: 开始解析 {len(candidates)} 个候选子域名（base={target_base}）')

        batch_results = self.resolve_batch(candidates, show_progress)
        results.update(batch_results)

        if self.recursive and depth < self.recursive_depth and self._budget[0] > 0:
            logger.info(f'第 {depth} 层: 发现 {len(batch_results)} 个子域名，继续递归...')

            # 递归扇出限制：每层最多对 N 个子域名继续递归
            bases = sorted(batch_results)
            if self.recursive_max_fanout and len(bases) > self.recursive_max_fanout:
                logger.warning(
                    f'递归扇出限制: {len(bases)} → {self.recursive_max_fanout}'
                    f'（跳过 {len(bases) - self.recursive_max_fanout} 个子域名）'
                )
                bases = bases[:self.recursive_max_fanout]

            for subdomain in bases:
                try:
                    subdomain_obj = Domain(subdomain)
                    base_domain = subdomain_obj.registered()
                    if base_domain != self.domain:
                        logger.debug(f'跳过跨域: {subdomain} -> {base_domain}')
                        continue

                    new_depth = depth + 1
                    logger.info(f'递归爆破: {subdomain} (第 {new_depth} 层)')
                    sub_brute = Brute(
                        self.domain,
                        {
                            'concurrent': self.concurrent,
                            'recursive': True,
                            'recursive_depth': self.recursive_depth,
                            'recursive_max_fanout': self.recursive_max_fanout,
                            'recursive_max_candidates': self.recursive_max_candidates,
                            'wildcard_check': False,
                            'wildcard_deal': self.wildcard_deal,
                            'wildcard_probes': self.wildcard_probes,
                            'wildcard_cidr': self.wildcard_cidr,
                        }
                    )
                    # 共享候选预算，限制整个递归树的查询总量
                    sub_brute._budget = self._budget
                    # 继承父级泛解析结果，并检测嵌套泛解析（如 *.dev.example.com）
                    merged_info = self._wildcard_info
                    if self.wildcard_check:
                        nested_info = self._merge_nested_wildcard(subdomain)
                        if nested_info:
                            merged_info = nested_info
                    sub_brute._wildcard_info = merged_info
                    sub_brute._wildcard_ips = set(merged_info.ips) if merged_info else set()
                    # 以找到的子域名为新基础域名，生成更深层候选
                    sub_results = sub_brute._run_recursive(
                        words, new_depth, show_progress, base=subdomain
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