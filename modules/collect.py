"""
收集调度器模块
负责协调各子域收集模块的执行
"""

import time
from typing import Optional, Set, List, Dict, Any

from config.logging import logger
from common.domain import Domain


collect_config = {
    'enabled': True,
    'module_timeout': 120,
    'max_concurrent': 50,
    'save_module_result': False,
}


def set_collect_config(config: dict):
    """设置收集调度器全局配置"""
    collect_config.update(config)


class Collect:
    """
    子域收集调度器

    负责协调搜索引擎、证书查询、数据集查询等模块的子域收集
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化收集调度器

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        self.domain = domain
        self.config = config or {}
        self.module_timeout = self.config.get('module_timeout', collect_config.get('module_timeout', 120))
        self.max_concurrent = self.config.get('max_concurrent', collect_config.get('max_concurrent', 50))
        self.save_module_result = self.config.get('save_module_result', collect_config.get('save_module_result', False))

        self.domain_obj = Domain(domain)
        self.registered_domain = self.domain_obj.registered()

        self.subdomains: Set[str] = set()
        self.results: List[Dict[str, Any]] = list()
        self.modules_results: Dict[str, Set[str]] = {}

        self.start_time = time.time()
        self.end_time = None
        self.elapse = None

        self.search_modules: List[Any] = []
        self.certificate_modules: List[Any] = []
        self.dataset_modules: List[Any] = []

        self._init_modules()

    def _init_modules(self):
        """初始化各模块"""
        logger.debug(f'初始化 {self.domain} 的收集模块')

    def run(self) -> List[str]:
        """
        执行收集任务

        :return: 子域名列表
        """
        logger.info(f'开始收集 {self.domain} 的子域名')
        self.start_time = time.time()

        self._run_search_modules()
        self._run_certificate_modules()
        self._run_dataset_modules()

        self.end_time = time.time()
        self.elapse = round(self.end_time - self.start_time, 1)
        logger.info(f'收集完成，共发现 {len(self.subdomains)} 个子域名，耗时 {self.elapse} 秒')

        return list(self.subdomains)

    def _run_search_modules(self):
        """执行搜索引擎模块收集"""
        if not self.search_modules:
            return
        logger.info(f'开始执行搜索引擎模块，共 {len(self.search_modules)} 个')

    def _run_certificate_modules(self):
        """执行证书查询模块收集"""
        if not self.certificate_modules:
            return
        logger.info(f'开始执行证书查询模块，共 {len(self.certificate_modules)} 个')

    def _run_dataset_modules(self):
        """执行数据集查询模块收集"""
        if not self.dataset_modules:
            return
        logger.info(f'开始执行数据集查询模块，共 {len(self.dataset_modules)} 个')

    def add_subdomains(self, subdomains: Set[str], module_name: str = 'unknown'):
        """
        添加子域名

        :param Set[str] subdomains: 子域名集合
        :param str module_name: 来源模块名称
        """
        if not subdomains:
            return

        old_count = len(self.subdomains)
        self.subdomains.update(subdomains)
        new_count = len(self.subdomains)

        self.modules_results[module_name] = subdomains
        logger.debug(f'{module_name} 模块发现 {new_count - old_count} 个新子域名')

    def get_results(self) -> List[Dict[str, Any]]:
        """
        获取最终结果

        :return: 结果列表
        """
        return self.results

    def get_module_results(self) -> Dict[str, Set[str]]:
        """
        获取各模块的收集结果

        :return: 模块名称到子域名集合的字典
        """
        return self.modules_results