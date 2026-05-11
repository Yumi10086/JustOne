"""
子域爆破模块
"""

import time
from pathlib import Path
from typing import Optional, Set, List

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

        self._wildcard_ips: Set[str] = set()

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
        words = wordlist or self.wordlist_lines
        candidates = []

        for word in words:
            if not word:
                continue
            candidate = f'{word}.{self.domain}'
            candidates.append(candidate)

        logger.debug(f'生成 {len(candidates)} 个候选子域名')
        return candidates

    def resolve_batch(self, candidates: List[str]) -> Set[str]:
        """
        批量解析候选子域名

        :param List[str] candidates: 候选子域名列表
        :return: 有效子域名集合
        """
        results = set()

        for candidate in candidates:
            try:
                info = resolve.resolve_domain(candidate)
                if info and info.get('ip'):
                    if self.wildcard_deal and self._wildcard_ips:
                        if info['ip'] in self._wildcard_ips:
                            continue
                    results.add(candidate)
            except Exception:
                pass

        return results

    def run(self, wordlist: Optional[List[str]] = None) -> Set[str]:
        """
        执行爆破

        :param List[str] wordlist: 可选的字典列表
        :return: 发现的子域名集合
        """
        logger.info(f'开始爆破子域名: {self.domain}')
        self.start_time = time.time()

        if not self.load_wordlist():
            return set()

        if self.check_wildcard():
            logger.info(f'检测到泛解析，将跳过相同 IP 的结果')

        candidates = self.generate_candidates(wordlist)
        logger.info(f'开始解析 {len(candidates)} 个候选子域名')

        self.subdomains = self.resolve_batch(candidates)

        self.end_time = time.time()
        self.elapse = round(self.end_time - self.start_time, 1)
        logger.info(f'爆破完成，发现 {len(self.subdomains)} 个子域名，耗时 {self.elapse} 秒')

        return self.subdomains

    def get_elapse(self) -> Optional[float]:
        """
        获取执行耗时

        :return: 执行耗时（秒）
        """
        return self.elapse