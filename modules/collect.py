"""
收集调度器模块
负责协调各子域收集模块的执行
"""

import time
import asyncio
import threading
import uuid
from typing import Optional, Set, List, Dict, Any, Type

from config.logging import logger
from common.domain import Domain
from common import resolve


collect_config = {
    'enabled': True,
    'module_timeout': 120,
    'max_concurrent': 25,
    'save_module_result': False,
    'enable_search': True,
    'enable_certificate': True,
    'enable_dataset': True,
    'enable_intelligence': True,
    # 按 source 名称覆盖默认超时（秒）。Playwright 模块 / 慢速 API 需要更长时间。
    'module_timeout_override': {
        'search.yahoo.com': 300,
        'virustotal': 1200,
    },
    # 收集完成后对结果进行泛解析 DNS 过滤
    'wildcard_filter': True,
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
        self.module_timeout_override = self.config.get('module_timeout_override', collect_config.get('module_timeout_override', {}))
        self.max_concurrent = self.config.get('max_concurrent', collect_config.get('max_concurrent', 50))
        self.save_module_result = self.config.get('save_module_result', collect_config.get('save_module_result', False))
        self.enable_search = self.config.get('enable_search', collect_config.get('enable_search', True))
        self.enable_certificate = self.config.get('enable_certificate', collect_config.get('enable_certificate', True))
        self.enable_dataset = self.config.get('enable_dataset', collect_config.get('enable_dataset', True))
        self.enable_intelligence = self.config.get('enable_intelligence', collect_config.get('enable_intelligence', True))
        self.wildcard_filter = self.config.get('wildcard_filter', collect_config.get('wildcard_filter', True))
        self._wildcard_ip: Optional[str] = None

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
        执行收集任务（同步入口）

        内部通过 asyncio.run 驱动异步调度器。
        注意：不要在已有事件循环中调用此方法，应直接 await run_async()。
        :return: 子域名列表
        """
        return asyncio.run(self.run_async())

    # 废弃：保留用于兼容，新调度器使用 _run_module_async
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

    async def _run_module_async(self, module: Any) -> Optional[tuple]:
        """
        异步执行单个模块（带超时保护，支持按 source 覆盖超时）

        同步模块通过 daemon 线程执行，超时后线程被放弃
        （其后续日志不影响主流程）。

        :param module: 模块实例
        :return: (子域名集合, 耗时) 或 None
        """
        source = getattr(module, 'source', 'unknown')
        timeout = self.module_timeout_override.get(source, self.module_timeout)

        try:
            logger.info(f'执行 {source} 模块（超时: {timeout}秒）')
            module_start = time.time()

            if hasattr(module, 'run_async') and asyncio.iscoroutinefunction(module.run_async):
                result = await asyncio.wait_for(
                    module.run_async(), timeout=timeout
                )
            else:
                # 同步模块：daemon 线程 + join(timeout)，超时后放弃线程
                result, exception = await self._run_sync_in_thread(
                    module, timeout
                )
                if exception:
                    raise exception

            module_elapse = round(time.time() - module_start, 1)
            logger.info(
                f'{source} 模块完成，发现 {len(result)} 个子域名，'
                f'耗时 {module_elapse} 秒'
            )
            return (result, module_elapse)

        except asyncio.TimeoutError:
            logger.error(
                f'{source} 模块执行超时（{timeout}秒），跳过'
            )
            return None
        except Exception as e:
            logger.error(f'{source} 模块执行出错: {e}')
            return None

    async def _run_sync_in_thread(self, module: Any, timeout: float):
        """
        在 daemon 线程中执行同步模块，超时后放弃线程。

        :param module: 模块实例
        :param float timeout: 超时秒数
        :return: (result, exception) — 正常时 exception 为 None
        :raises asyncio.TimeoutError: 线程未在 timeout 内完成
        """
        loop = asyncio.get_running_loop()
        result = None
        exception = None
        done = threading.Event()

        def _run():
            nonlocal result, exception
            try:
                result = module.run()
            except Exception as e:
                exception = e
            finally:
                done.set()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        # 在线程池中执行 join（避免阻塞事件循环）
        await loop.run_in_executor(None, thread.join, timeout)

        if not done.is_set():
            # 超时：线程仍在运行（daemon，进程退出时自动终止）
            raise asyncio.TimeoutError()

        return result, exception

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

    async def _detect_wildcard_ip(self) -> Optional[str]:
        """
        检测目标域名是否存在泛解析，返回泛解析 IP。

        构造随机不存在的子域名进行 DNS 解析，
        如果解析成功则说明存在泛解析，返回解析到的 IP。
        :return: 泛解析 IP，未检测到返回 None
        """
        prefix = f'_wc_{uuid.uuid4().hex[:12]}'
        test_domain = f'{prefix}.{self.registered_domain}'
        logger.debug(f'检测泛解析: {test_domain}')

        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(
            None, resolve.resolve_domain, test_domain
        )
        if info and info.get('resolve') and info.get('ip'):
            wildcard_ip = info['ip']
            logger.warning(
                f'检测到泛解析 — {test_domain} 解析到 {wildcard_ip}'
            )
            return wildcard_ip
        logger.debug('未检测到泛解析')
        return None

    async def _filter_wildcard_subdomains(self, wildcard_ip: str) -> int:
        """
        并发解析所有已收集子域名，移除解析到泛解析 IP 的条目。

        :param str wildcard_ip: 泛解析 IP 地址
        :return: 被移除的子域名数量
        """
        subdomains = list(self.subdomains)
        total = len(subdomains)
        logger.info(f'泛解析过滤: 检查 {total} 个子域名，目标 IP: {wildcard_ip}')

        loop = asyncio.get_running_loop()
        semaphore = asyncio.Semaphore(50)  # 限制并发 DNS 查询

        async def resolve_one(subdomain: str) -> Optional[str]:
            async with semaphore:
                info = await loop.run_in_executor(
                    None, resolve.resolve_domain, subdomain
                )
                if info and info.get('ip') == wildcard_ip:
                    return subdomain
            return None

        tasks = [resolve_one(s) for s in subdomains]
        results = await asyncio.gather(*tasks)

        to_remove = {r for r in results if r is not None}
        if to_remove:
            self.subdomains.difference_update(to_remove)
            logger.warning(
                f'泛解析过滤: 移除了 {len(to_remove)} 个泛解析子域名，'
                f'剩余 {len(self.subdomains)} 个'
            )
        else:
            logger.debug('泛解析过滤: 无匹配子域名')
        return len(to_remove)

    async def run_async(self) -> List[str]:
        """
        异步执行收集任务（asyncio 原生入口）

        并发调度所有模块类型，每个模块独立超时保护。
        先检测泛解析，若存在则限制高耗时模块的拉取量。
        :return: 子域名列表
        """
        logger.info(f'开始收集 {self.domain} 的子域名')
        self.start_time = time.time()

        all_modules = (
            self.search_modules + self.certificate_modules +
            self.dataset_modules + self.dnsquery_modules +
            self.intelligence_modules
        )

        # 先检测泛解析：若存在则限制 VirusTotal 等高频模块的拉取页数
        if self.wildcard_filter:
            wildcard_ip = await self._detect_wildcard_ip()
            if wildcard_ip:
                self._wildcard_ip = wildcard_ip
                for module in all_modules:
                    source = getattr(module, 'source', '')
                    if source == 'virustotal' and hasattr(module, 'max_pages'):
                        old = module.max_pages
                        module.max_pages = min(old, 5)
                        logger.info(
                            f'检测到泛解析，{source} max_pages: {old} → {module.max_pages}'
                        )
                        break
        else:
            self._wildcard_ip = None

        total = len(all_modules)
        logger.info(f'并发执行 {total} 个模块（并发数: {self.max_concurrent}）')

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def _run_with_semaphore(module):
            async with semaphore:
                return await self._run_module_async(module)

        tasks = [_run_with_semaphore(m) for m in all_modules if m is not None]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for module, result in zip(all_modules, results):
            if isinstance(result, Exception):
                module_name = getattr(module, 'module', 'unknown')
                logger.error(f'{module_name} 模块异常: {result}')
                continue
            if result is None:
                continue
            module_name = getattr(module, 'module', 'unknown')
            self.add_subdomains(result[0], module_name)

        for module in all_modules:
            if hasattr(module, 'cleanup'):
                try:
                    await asyncio.wait_for(module.cleanup(), timeout=5)
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

        # 泛解析过滤：移除解析到泛解析 IP 的子域名
        if self._wildcard_ip and len(self.subdomains) >= 10:
            await self._filter_wildcard_subdomains(self._wildcard_ip)

        self.end_time = time.time()
        self.elapse = round(self.end_time - self.start_time, 1)
        logger.info(
            f'收集完成，共发现 {len(self.subdomains)} 个子域名，'
            f'耗时 {self.elapse} 秒'
        )

        return list(self.subdomains)

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