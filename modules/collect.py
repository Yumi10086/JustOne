"""
收集调度器模块
负责协调各子域收集模块的执行
"""

import time
import threading
from typing import Optional, Set, List, Dict, Any, Type

from config.logging import logger
from common.domain import Domain


collect_config = {
    'enabled': True,
    'module_timeout': 120,
    'max_concurrent': 50,
    'save_module_result': False,
    'enable_search': True,
    'enable_certificate': True,
    'enable_dataset': True,
    'enable_intelligence': True,
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
        self.enable_search = self.config.get('enable_search', collect_config.get('enable_search', True))
        self.enable_certificate = self.config.get('enable_certificate', collect_config.get('enable_certificate', True))
        self.enable_dataset = self.config.get('enable_dataset', collect_config.get('enable_dataset', True))
        self.enable_intelligence = self.config.get('enable_intelligence', collect_config.get('enable_intelligence', True))

        self.domain_obj = Domain(domain)
        self.registered_domain = self.domain_obj.registered()

        if not self.registered_domain:
            raise ValueError(f'无法解析目标域名: {domain}，请检查域名格式')

        self.subdomains: Set[str] = set()
        self.results: List[Dict[str, Any]] = list()
        self.modules_results: Dict[str, Set[str]] = {}

        self.start_time = time.time()
        self.end_time = None
        self.elapse = None

        self.search_modules: List[Any] = []
        self.certificate_modules: List[Any] = []
        self.dataset_modules: List[Any] = []
        self.dnsquery_modules: List[Any] = []
        self.intelligence_modules: List[Any] = []

        self._init_modules()

    def _init_modules(self):
        """初始化各模块"""
        logger.debug(f'初始化 {self.domain} 的收集模块')
        self._init_search_modules()
        self._init_certificate_modules()
        self._init_dataset_modules()
        self._init_dnsquery_modules()
        self._init_intelligence_modules()

    def _init_search_modules(self):
        """初始化搜索引擎模块"""
        if not self.enable_search:
            return

        try:
            from modules.search import (
                BaiduSearch, BingSearch, FoFa, Hunter, ShodanAPI,
                ZoomEyeAPI, GithubAPI, Google, Yahoo, Yandex,
                SoSearch, SogouSearch,
            )
            self.search_modules = [
                BaiduSearch(self.registered_domain, self.config),
                BingSearch(self.registered_domain, self.config),
                FoFa(self.registered_domain, self.config),
                Hunter(self.registered_domain, self.config),
                ShodanAPI(self.registered_domain, self.config),
                ZoomEyeAPI(self.registered_domain, self.config),
                GithubAPI(self.registered_domain, self.config),
                Google(self.registered_domain, self.config),
                Yahoo(self.registered_domain, self.config),
                Yandex(self.registered_domain, self.config),
                SoSearch(self.registered_domain, self.config),
                SogouSearch(self.registered_domain, self.config),
            ]
            logger.debug(f'已加载 {len(self.search_modules)} 个搜索引擎模块')
        except ImportError as e:
            logger.warning(f'导入搜索模块失败: {e}')

    def _init_certificate_modules(self):
        """初始化证书查询模块"""
        if not self.enable_certificate:
            return

        try:
            from modules.certificates import Crtsh, CertSpotter, Censys
            self.certificate_modules = [
                Crtsh(self.registered_domain, self.config),
                CertSpotter(self.registered_domain, self.config),
                Censys(self.registered_domain, self.config),
            ]
            logger.debug(f'已加载 {len(self.certificate_modules)} 个证书查询模块')
        except ImportError as e:
            logger.warning(f'导入证书模块失败: {e}')

    def _init_dataset_modules(self):
        """初始化数据集查询模块"""
        if not self.enable_dataset:
            return

        try:
            from modules.datasets import (
                LeakIX, Anubis, ChinazAPI,
                Chinaz, CirclAPI, CloudFlareAPI, DNSDumpster,
                FullHuntAPI, HackerTarget, IP138, NetCraft,
                PassiveDnsAPI, RapidDNS, Robtex,
                SecurityTrailsAPI,
            )
            self.dataset_modules = [
                LeakIX(self.registered_domain, self.config),
                Anubis(self.registered_domain, self.config),
                ChinazAPI(self.registered_domain, self.config),
                Chinaz(self.registered_domain, self.config),
                CirclAPI(self.registered_domain, self.config),
                CloudFlareAPI(self.registered_domain, self.config),
                DNSDumpster(self.registered_domain, self.config),
                FullHuntAPI(self.registered_domain, self.config),
                HackerTarget(self.registered_domain, self.config),
                IP138(self.registered_domain, self.config),
                NetCraft(self.registered_domain, self.config),
                PassiveDnsAPI(self.registered_domain, self.config),
                RapidDNS(self.registered_domain, self.config),
                Robtex(self.registered_domain, self.config),
                SecurityTrailsAPI(self.registered_domain, self.config),
            ]
            logger.debug(f'已加载 {len(self.dataset_modules)} 个数据集查询模块')
        except ImportError as e:
            logger.warning(f'导入数据集模块失败: {e}')

    def _init_dnsquery_modules(self):
        """初始化 DNS 查询模块"""
        try:
            from modules.dnsquery import MXQuery, QueryNS, QuerySOA, QuerySPF, QueryTXT
            self.dnsquery_modules = [
                MXQuery(self.registered_domain, self.config),
                QueryNS(self.registered_domain, self.config),
                QuerySOA(self.registered_domain, self.config),
                QuerySPF(self.registered_domain, self.config),
                QueryTXT(self.registered_domain, self.config),
            ]
            logger.debug(f'已加载 {len(self.dnsquery_modules)} 个 DNS 查询模块')
        except ImportError as e:
            logger.warning(f'导入 DNS 查询模块失败: {e}')

    def _init_intelligence_modules(self):
        """初始化威胁情报模块"""
        if not self.enable_intelligence:
            return

        try:
            from modules.intelligence import (
                AlienVaultOTX, URLScan, ThreatBook,
                VirusTotalAPI, ThreatMiner,
            )
            self.intelligence_modules = [
                AlienVaultOTX(self.registered_domain, self.config),
                URLScan(self.registered_domain, self.config),
                ThreatBook(self.registered_domain, self.config),
                VirusTotalAPI(self.registered_domain, self.config),
                ThreatMiner(self.registered_domain, self.config),
            ]
            logger.debug(f'已加载 {len(self.intelligence_modules)} 个威胁情报模块')
        except ImportError as e:
            logger.warning(f'导入威胁情报模块失败: {e}')

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
        self._run_dnsquery_modules()
        self._run_intelligence_modules()

        self.end_time = time.time()
        self.elapse = round(self.end_time - self.start_time, 1)
        logger.info(f'收集完成，共发现 {len(self.subdomains)} 个子域名，耗时 {self.elapse} 秒')

        return list(self.subdomains)

    def _run_module(self, module: Any) -> Set[str]:
        """
        执行单个模块（带超时保护）

        :param module: 模块实例
        :return: 发现的子域名集合
        """
        module_name = getattr(module, 'module', 'Unknown')
        source = getattr(module, 'source', 'unknown')

        result: Set[str] = set()
        exception: Optional[Exception] = None

        def _run():
            nonlocal result, exception
            try:
                result = module.run()
            except Exception as e:
                exception = e

        try:
            logger.info(f'执行 {source} 模块')
            module_start = time.time()

            thread = threading.Thread(target=_run, daemon=True)
            thread.start()
            thread.join(timeout=self.module_timeout)

            if thread.is_alive():
                logger.error(f'{source} 模块执行超时（{self.module_timeout}秒），跳过')
                return set()

            if exception:
                raise exception

            module_elapse = round(time.time() - module_start, 1)
            logger.info(f'{source} 模块完成，发现 {len(result)} 个子域名，耗时 {module_elapse} 秒')
            return result
        except Exception as e:
            logger.error(f'{source} 模块执行出错: {e}')
            return set()

    def _run_search_modules(self):
        """执行搜索引擎模块收集"""
        if not self.search_modules:
            logger.debug('未配置搜索引擎模块')
            return

        logger.info(f'开始执行搜索引擎模块，共 {len(self.search_modules)} 个')
        for module in self.search_modules:
            subdomains = self._run_module(module)
            module_name = getattr(module, 'module', 'search')
            self.add_subdomains(subdomains, module_name)

    def _run_certificate_modules(self):
        """执行证书查询模块收集"""
        if not self.certificate_modules:
            logger.debug('未配置证书查询模块')
            return

        logger.info(f'开始执行证书查询模块，共 {len(self.certificate_modules)} 个')
        for module in self.certificate_modules:
            subdomains = self._run_module(module)
            module_name = getattr(module, 'module', 'certificate')
            self.add_subdomains(subdomains, module_name)

    def _run_dataset_modules(self):
        """执行数据集查询模块收集"""
        if not self.dataset_modules:
            logger.debug('未配置数据集查询模块')
            return

        logger.info(f'开始执行数据集查询模块，共 {len(self.dataset_modules)} 个')
        for module in self.dataset_modules:
            subdomains = self._run_module(module)
            module_name = getattr(module, 'module', 'dataset')
            self.add_subdomains(subdomains, module_name)

    def _run_dnsquery_modules(self):
        """执行 DNS 查询模块收集"""
        if not self.dnsquery_modules:
            logger.debug('未配置 DNS 查询模块')
            return

        logger.info(f'开始执行 DNS 查询模块，共 {len(self.dnsquery_modules)} 个')
        for module in self.dnsquery_modules:
            subdomains = self._run_module(module)
            module_name = getattr(module, 'module', 'dnsquery')
            self.add_subdomains(subdomains, module_name)

    def _run_intelligence_modules(self):
        """执行威胁情报模块收集"""
        if not self.intelligence_modules:
            logger.debug('未配置威胁情报模块')
            return

        logger.info(f'开始执行威胁情报模块，共 {len(self.intelligence_modules)} 个')
        for module in self.intelligence_modules:
            subdomains = self._run_module(module)
            module_name = getattr(module, 'module', 'intelligence')
            self.add_subdomains(subdomains, module_name)

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

    def add_module(self, module_class: Type, module_type: str = 'search'):
        """
        添加自定义模块

        :param Type module_class: 模块类
        :param str module_type: 模块类型 ('search', 'certificate', 'dataset')
        """
        module_instance = module_class(self.registered_domain, self.config)

        if module_type == 'search':
            self.search_modules.append(module_instance)
        elif module_type == 'certificate':
            self.certificate_modules.append(module_instance)
        elif module_type == 'dataset':
            self.dataset_modules.append(module_instance)

        logger.debug(f'添加自定义模块: {getattr(module_class, "__name__", "Unknown")}')

    def get_results(self) -> List[Dict[str, Any]]:
        """
        获取最终结果

        :return: 结果字典列表
        """
        return [{'subdomain': s, 'module': 'unknown'} for s in sorted(self.subdomains)]

    def get_module_results(self) -> Dict[str, Set[str]]:
        """
        获取各模块的收集结果

        :return: 模块名称到子域名集合的字典
        """
        return self.modules_results

    def get_summary(self) -> Dict[str, Any]:
        """
        获取收集摘要

        :return: 摘要信息字典
        """
        return {
            'domain': self.domain,
            'registered_domain': self.registered_domain,
            'total_subdomains': len(self.subdomains),
            'modules_count': {
                'search': len(self.search_modules),
                'certificate': len(self.certificate_modules),
                'dataset': len(self.dataset_modules),
                'dnsquery': len(self.dnsquery_modules),
                'intelligence': len(self.intelligence_modules),
            },
            'modules_results': {name: len(subs) for name, subs in self.modules_results.items()},
            'elapse': self.elapse,
        }