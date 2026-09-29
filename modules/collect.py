"""
收集调度器模块
负责协调各子域收集模块的执行
"""

import time
import asyncio
import functools
import importlib
import threading
from typing import Optional, Set, List, Dict, Any, Type

from config.logging import logger
from common.domain import Domain
from common.wildcard import WildcardInfo, detect_wildcard, filter_subdomains


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
    # 泛解析探测次数（随机标签数量）
    'wildcard_probes': 3,
    # 泛解析过滤时是否启用同 /24 网段匹配
    'wildcard_cidr': False,
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
        self.module_timeout = self._cfg('module_timeout', 120)
        self.module_timeout_override = self._cfg('module_timeout_override', {})
        self.max_concurrent = self._cfg('max_concurrent', 25)
        self.save_module_result = self._cfg('save_module_result', False)
        self.enable_search = self._cfg('enable_search', True)
        self.enable_certificate = self._cfg('enable_certificate', True)
        self.enable_dataset = self._cfg('enable_dataset', True)
        self.enable_intelligence = self._cfg('enable_intelligence', True)
        self.wildcard_filter = self._cfg('wildcard_filter', True)
        self.wildcard_probes = self._cfg('wildcard_probes', 3)
        self.wildcard_cidr = self._cfg('wildcard_cidr', False)
        self._wildcard_info: Optional[WildcardInfo] = None

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

    def _cfg(self, key: str, default: Any = None) -> Any:
        """
        读取配置：实例 config 优先，其次全局 collect_config

        :param str key: 配置键
        :param default: 默认值
        :return: 配置值
        """
        return self.config.get(key, collect_config.get(key, default))

    # 模块类别注册表: (类别名, 启用开关配置键, 模块包路径, 模块类名列表)
    # dnsquery 无独立开关，始终加载
    _MODULE_SPECS = (
        ('search', 'enable_search', 'modules.search',
         ('BaiduSearch', 'BingSearch', 'FoFa', 'Hunter', 'ShodanAPI',
          'ZoomEyeAPI', 'GithubAPI', 'Google', 'Yahoo', 'Yandex',
          'SoSearch', 'SogouSearch')),
        ('certificate', 'enable_certificate', 'modules.certificates',
         ('Crtsh', 'CertSpotter', 'Censys')),
        ('dataset', 'enable_dataset', 'modules.datasets',
         ('LeakIX', 'Anubis', 'ChinazAPI', 'Chinaz', 'CirclAPI',
          'CloudFlareAPI', 'DNSDumpster', 'FullHuntAPI', 'HackerTarget',
          'IP138', 'NetCraft', 'PassiveDnsAPI', 'RapidDNS', 'Robtex',
          'SecurityTrailsAPI')),
        ('dnsquery', None, 'modules.dnsquery',
         ('MXQuery', 'QueryNS', 'QuerySOA', 'QuerySPF', 'QueryTXT')),
        ('intelligence', 'enable_intelligence', 'modules.intelligence',
         ('AlienVaultOTX', 'URLScan', 'ThreatBook', 'VirusTotalAPI', 'ThreatMiner')),
    )

    def _init_modules(self):
        """初始化各模块（按类别注册表批量加载）"""
        logger.debug(f'初始化 {self.domain} 的收集模块')

        for category, enable_key, package, class_names in self._MODULE_SPECS:
            if enable_key and not getattr(self, enable_key):
                continue
            try:
                module_pkg = importlib.import_module(package)
                classes = [getattr(module_pkg, name) for name in class_names]
                setattr(
                    self, f'{category}_modules',
                    [cls(self.registered_domain, self.config) for cls in classes],
                )
                logger.debug(f'已加载 {len(classes)} 个 {category} 模块')
            except (ImportError, AttributeError) as e:
                logger.warning(f'导入 {category} 模块失败: {e}')

    def run(self) -> List[str]:
        """
        执行收集任务（同步入口）

        内部通过 asyncio.run 驱动异步调度器。
        注意：不要在已有事件循环中调用此方法，应直接 await run_async()。
        :return: 子域名列表
        """
        return asyncio.run(self.run_async())

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

    async def _detect_wildcard(self) -> Optional[WildcardInfo]:
        """
        检测目标域名是否存在泛解析

        通过多随机标签探测，若存在泛解析则返回检测结果。
        :return: 泛解析检测结果，未检测到返回 None
        """
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(
            None,
            functools.partial(
                detect_wildcard,
                self.registered_domain,
                probes=self.wildcard_probes,
            ),
        )
        if info and info.detected:
            return info
        logger.debug('未检测到泛解析')
        return None

    async def _filter_wildcard_subdomains(self, info: WildcardInfo) -> int:
        """
        并发解析所有已收集子域名，移除属于泛解析的条目。

        :param WildcardInfo info: 泛解析检测结果
        :return: 被移除的子域名数量
        """
        total = len(self.subdomains)
        logger.info(f'泛解析过滤: 检查 {total} 个子域名，泛解析 IP: {sorted(info.ips)}')

        loop = asyncio.get_running_loop()
        kept, removed = await loop.run_in_executor(
            None,
            functools.partial(
                filter_subdomains,
                list(self.subdomains),
                info,
                concurrent=50,
                include_cidr=self.wildcard_cidr,
            ),
        )

        self.subdomains = kept
        if removed:
            logger.warning(
                f'泛解析过滤: 移除了 {len(removed)} 个泛解析子域名，'
                f'剩余 {len(self.subdomains)} 个'
            )
        else:
            logger.debug('泛解析过滤: 无匹配子域名')
        return len(removed)

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
            wildcard_info = await self._detect_wildcard()
            if wildcard_info:
                self._wildcard_info = wildcard_info
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
            self._wildcard_info = None

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

        # 泛解析过滤：移除属于泛解析的子域名
        if self._wildcard_info and len(self.subdomains) >= 10:
            await self._filter_wildcard_subdomains(self._wildcard_info)

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
        :param str module_type: 模块类别 ('search', 'certificate', 'dataset', 'dnsquery', 'intelligence')
        """
        attr = f'{module_type}_modules'
        if not hasattr(self, attr):
            logger.warning(f'未知模块类别: {module_type}')
            return

        module_instance = module_class(self.registered_domain, self.config)
        getattr(self, attr).append(module_instance)
        logger.debug(f'添加自定义模块: {getattr(module_class, "__name__", "Unknown")}')

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