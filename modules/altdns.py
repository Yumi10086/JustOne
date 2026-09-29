"""
子域置换模块
基于已有子域名，通过置换规则生成新的候选子域名并进行 DNS 验证
"""

import time
import re
from pathlib import Path
from typing import Optional, Set, List

from config.logging import logger
from common import resolve
from common import utils
from common.wildcard import WildcardInfo, detect_wildcard


altdns_config = {
    'enabled': True,
    'concurrent': 50,
    'wordlist': None,
    'prefix': True,
    'suffix': True,
    'number': True,
    'insert': True,
    'wildcard_check': True,
    'wildcard_deal': True,
    'wildcard_probes': 3,
    'wildcard_cidr': False,
}


def set_altdns_config(config: dict):
    """设置置换模块全局配置"""
    altdns_config.update(config)


class Altdns:
    """
    子域置换模块

    对已有子域名应用多种置换规则生成新候选，
    再通过 DNS 解析验证有效性。
    """

    def __init__(self, domain: str, subdomains: Set[str], config: Optional[dict] = None):
        """
        初始化置换模块

        :param str domain: 目标域名
        :param Set[str] subdomains: 已知子域名集合
        :param dict config: 可选配置字典
        """
        self.domain = domain
        self.subdomains = subdomains
        self.config = {**altdns_config, **(config or {})}

        self.concurrent = self.config.get('concurrent', altdns_config.get('concurrent', 50))
        self.wordlist_path = self.config.get('wordlist', altdns_config.get('wordlist'))
        self.enable_prefix = self.config.get('prefix', True)
        self.enable_suffix = self.config.get('suffix', True)
        self.enable_number = self.config.get('number', True)
        self.enable_insert = self.config.get('insert', True)
        self.wildcard_check = self.config.get('wildcard_check', altdns_config.get('wildcard_check', True))
        self.wildcard_deal = self.config.get('wildcard_deal', altdns_config.get('wildcard_deal', True))
        self.wildcard_probes = self.config.get('wildcard_probes', altdns_config.get('wildcard_probes', 3))
        self.wildcard_cidr = self.config.get('wildcard_cidr', altdns_config.get('wildcard_cidr', False))

        self.new_subdomains: Set[str] = set()
        self.wordlist_lines: List[str] = []
        self._wildcard_info: Optional[WildcardInfo] = None

        self.start_time = time.time()
        self.end_time = None
        self.elapse = None

    def load_wordlist(self) -> bool:
        """
        加载置换词表

        :return: 是否加载成功
        """
        if self.wordlist_path is None:
            project_root = Path(__file__).parent.parent
            default_wordlist = project_root / 'data' / 'altdns_wordlist.txt'
            if default_wordlist.exists():
                self.wordlist_path = default_wordlist
            else:
                logger.warning(f'未找到默认置换词表: {default_wordlist}')
                return False

        wordlist_path = Path(self.wordlist_path)
        if not wordlist_path.exists():
            logger.error(f'置换词表文件不存在: {wordlist_path}')
            return False

        try:
            with open(wordlist_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.wordlist_lines = [
                    line.strip() for line in f
                    if line.strip() and not line.startswith('#')
                ]
            logger.info(f'加载置换词表成功，共 {len(self.wordlist_lines)} 个条目')
            return True
        except Exception as e:
            logger.error(f'加载置换词表失败: {e}')
            return False

    def _extract_label(self, subdomain: str) -> str:
        """
        从子域名中提取最左标签

        :param str subdomain: 完整子域名
        :return: 最左标签部分
        """
        suffix = f'.{self.domain}'
        if subdomain.endswith(suffix):
            return subdomain[:-len(suffix)]
        return subdomain

    def generate_candidates(self) -> Set[str]:
        """
        生成所有置换候选子域名

        :return: 候选子域名集合
        """
        if not self.wordlist_lines:
            return set()

        candidates = set()
        labels = {}

        for sub in self.subdomains:
            label = self._extract_label(sub)
            if not label:
                continue
            labels[sub] = label

        for sub, label in labels.items():
            if self.enable_prefix:
                for w in self.wordlist_lines:
                    candidates.add(f'{w}-{label}.{self.domain}')

            if self.enable_suffix:
                for w in self.wordlist_lines:
                    candidates.add(f'{label}-{w}.{self.domain}')

            if self.enable_number:
                for i in range(1, 11):
                    candidates.add(f'{label}{i}.{self.domain}')

            if self.enable_insert:
                for w in self.wordlist_lines:
                    if w and len(w) < len(label):
                        if label.startswith(w):
                            rest = label[len(w):]
                            if rest and rest[0] != '-':
                                candidates.add(f'{w}-{rest}.{self.domain}')
                        if label.endswith(w):
                            head = label[:-len(w)]
                            if head and head[-1] != '-':
                                candidates.add(f'{head}-{w}.{self.domain}')

        candidates -= self.subdomains
        return candidates

    def resolve_batch(self, candidates: Set[str], show_progress: bool = True) -> Set[str]:
        """
        批量解析候选子域名

        :param Set[str] candidates: 候选子域名集合
        :param bool show_progress: 是否显示进度条
        :return: 有效子域名集合
        """
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
            return None

        results_list = utils.run_concurrent(
            candidates,
            resolve_one,
            max_workers=self.concurrent,
            desc='置换验证' if show_progress else None,
        )
        return {r for r in results_list if r}

    def run(self, show_progress: bool = True) -> Set[str]:
        """
        执行置换流程

        :param bool show_progress: 是否显示进度条
        :return: 新发现的子域名集合
        """
        logger.info(f'开始子域置换: {self.domain}')
        self.start_time = time.time()

        if not self.subdomains:
            logger.info('无可用的已知子域名，跳过置换')
            return set()

        if not self.load_wordlist():
            return set()

        candidates = self.generate_candidates()
        logger.info(f'生成 {len(candidates)} 个置换候选')

        if not candidates:
            logger.info('未生成任何候选')
            return set()

        if self.wildcard_check:
            self._wildcard_info = detect_wildcard(self.domain, probes=self.wildcard_probes)
            if self._wildcard_info.detected:
                logger.info('检测到泛解析，将过滤泛解析候选')

        self.new_subdomains = self.resolve_batch(candidates, show_progress)

        self.end_time = time.time()
        self.elapse = round(self.end_time - self.start_time, 1)
        logger.info(
            f'置换完成: 发现 {len(self.new_subdomains)} 个新子域名，'
            f'耗时 {self.elapse} 秒'
        )
        return self.new_subdomains

    def get_elapse(self) -> Optional[float]:
        """
        获取执行耗时

        :return: 执行耗时（秒）
        """
        return self.elapse


def run(domain: str, subdomains: Set[str], config: Optional[dict] = None) -> Set[str]:
    """模块执行入口"""
    module = Altdns(domain, subdomains, config)
    return module.run()
