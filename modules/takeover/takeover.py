# -*- coding: utf-8 -*-
"""
子域名接管检测主模块

负责 DNS CNAME 查询、指纹匹配和 HTTP 确认的编排。

注意：DNS 查询使用同步 dnspython（通过 @lru_cache 缓存结果），
HTTP 确认使用异步 aiohttp。check_subdomain() 是同步入口，
run() 是异步批量入口。
"""

import asyncio
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional, Set, List, Tuple

from tqdm import tqdm

import aiohttp
import dns.resolver

from modules.takeover.fingerprints import load_fingerprints, find_matching_fingerprint
from config.logging import logger


@dataclass
class TakeoverResult:
    """单个子域名的接管检测结果"""
    subdomain: str
    cname: Optional[str] = None
    service: Optional[str] = None
    severity: Optional[str] = None
    status: str = 'not_vulnerable'
    detail: dict = field(default_factory=dict)


RISK_ORDER = {'vulnerable': 0, 'likely': 1, 'not_vulnerable': 2, 'unknown': 3, 'error': 4}


class TakeoverCheck:
    """
    子域名接管检测器

    通过 DNS CNAME 查询 + HTTP 响应指纹双重确认来判定接管风险。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param domain: 目标域名
        :param config: 可选配置（fingerprint_file, concurrent, http_timeout, pre_check）
        """
        self.domain = domain
        self.config = config or {}
        fp_path = self.config.get('fingerprint_file')
        if isinstance(fp_path, str):
            fp_path = Path(fp_path)
        self.fingerprints = load_fingerprints(fp_path)
        self.concurrent = self.config.get('concurrent', 20)
        self.http_timeout = self.config.get('http_timeout', 10)
        self.pre_check_enabled = self.config.get('pre_check', True)

    # 公共 DNS 服务器（国内优先）
    _NAMESERVERS = ['223.5.5.5', '114.114.114.114', '1.1.1.1', '8.8.8.8']

    @staticmethod
    @lru_cache(maxsize=1024)
    def _resolve_cname(subdomain: str) -> Tuple[Optional[str], str]:
        """
        同步 DNS CNAME 查询（带 lru_cache）

        使用公共 DNS 服务器列表（国内优先），避免系统解析器速率限制。

        :param subdomain: 子域名
        :return: (cname_target, dns_status)
                 dns_status: NOERROR / NXDOMAIN / TIMEOUT / ERROR:msg
        """
        res = dns.resolver.Resolver()
        res.nameservers = TakeoverCheck._NAMESERVERS
        res.timeout = 8
        res.lifetime = 20
        try:
            answers = res.resolve(subdomain, 'CNAME')
            return (str(answers[0].target).rstrip('.'), 'NOERROR')
        except dns.resolver.NoAnswer:
            return (None, 'NOERROR')
        except dns.resolver.NXDOMAIN:
            return (None, 'NXDOMAIN')
        except dns.resolver.Timeout:
            return (None, 'TIMEOUT')
        except Exception as e:
            return (None, f'ERROR:{e}')

    @staticmethod
    @lru_cache(maxsize=2048)
    def _resolve_a(subdomain: str) -> Tuple[bool, str]:
        """
        同步 DNS A 记录查询（带 lru_cache），用于存活预检

        使用公共 DNS 服务器列表（国内优先），快速判断子域名是否存活。

        :param subdomain: 子域名
        :return: (is_alive, reason)
                 is_alive: True=存活（有 A 记录或 NoAnswer），False=已死
                 reason: OK / NXDOMAIN / TIMEOUT / NoAnswer / ERROR:msg
        """
        res = dns.resolver.Resolver()
        res.nameservers = TakeoverCheck._NAMESERVERS
        res.timeout = 5
        res.lifetime = 10
        try:
            res.resolve(subdomain, 'A')
            return (True, 'OK')
        except dns.resolver.NXDOMAIN:
            return (False, 'NXDOMAIN')
        except dns.resolver.Timeout:
            return (False, 'TIMEOUT')
        except dns.resolver.NoAnswer:
            # 域名存在但无 A 记录（可能仅 CNAME 或其他记录类型），仍视为存活
            return (True, 'NoAnswer')
        except Exception as e:
            return (False, f'ERROR:{e}')

    def _process_dns_result(self, subdomain: str, cname: Optional[str], dns_status: str) -> TakeoverResult:
        """
        处理 DNS 解析结果，返回 TakeoverResult（不含 HTTP 阶段）

        :param subdomain: 子域名
        :param cname: CNAME 目标
        :param dns_status: DNS 状态
        :return: TakeoverResult
        """
        if dns_status in ('TIMEOUT',) or dns_status.startswith('ERROR:'):
            return TakeoverResult(
                subdomain=subdomain, cname=cname, status='error',
                detail={'dns_status': dns_status, 'cname_matched': None}
            )
        if cname is None:
            return TakeoverResult(
                subdomain=subdomain, cname=None, status='not_vulnerable',
                detail={'dns_status': dns_status, 'cname_matched': None}
            )

        match_result = find_matching_fingerprint(cname, self.fingerprints)
        if match_result is None:
            return TakeoverResult(
                subdomain=subdomain, cname=cname, status='not_vulnerable',
                detail={'dns_status': dns_status, 'cname_matched': None}
            )

        service_id, fp, matched_pattern = match_result
        return TakeoverResult(
            subdomain=subdomain, cname=cname, service=service_id,
            severity=fp.get('severity'), status='unknown',
            detail={'dns_status': dns_status, 'cname_matched': matched_pattern}
        )

    async def _apply_http_check(self, result: TakeoverResult, fp: dict) -> TakeoverResult:
        """
        对已匹配指纹的结果执行 HTTP 确认

        :param result: DNS 阶段的结果
        :param fp: 指纹字典
        :return: 更新后的 TakeoverResult
        """
        http_check = fp.get('http_check', {})
        if http_check.get('enabled', True):
            http_result = await self._check_http(result.subdomain, fp)
            result.detail.update(http_result)
            result.status = http_result.get('judgment', 'unknown')
        else:
            result.status = 'likely'
        return result

    def check_subdomain(self, subdomain: str) -> TakeoverResult:
        """
        检查单个子域名的接管风险（同步入口）

        :param subdomain: 要检查的子域名
        :return: TakeoverResult
        """
        cname, dns_status = TakeoverCheck._resolve_cname(subdomain)
        result = self._process_dns_result(subdomain, cname, dns_status)

        if result.status in ('error', 'not_vulnerable'):
            return result

        fp = self.fingerprints.get(result.service)
        if not fp:
            return result

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        http_result = loop.run_until_complete(self._apply_http_check(result, fp))
        return http_result

    @staticmethod
    async def _check_http_path(
        session: aiohttp.ClientSession, subdomain: str, path: str,
        http_timeout: int = 10
    ) -> dict:
        """
        检查单一路径的 HTTP 响应

        :param session: aiohttp 会话
        :param subdomain: 子域名
        :param path: URL 路径
        :param http_timeout: 超时秒数
        :return: 含状态码/响应体/头部/错误的字典
        """
        url = f'https://{subdomain}{path}'
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=http_timeout),
                allow_redirects=True,
            ) as resp:
                body = await resp.text()
                return {
                    'status_code': resp.status,
                    'body': body,
                    'headers': dict(resp.headers),
                    'error': None,
                }
        except asyncio.TimeoutError:
            return {'status_code': 0, 'body': '', 'headers': {}, 'error': 'timeout'}
        except Exception as e:
            return {'status_code': 0, 'body': '', 'headers': {}, 'error': str(e)}

    @staticmethod
    def _check_fingerprint_match(http_check: dict, resp: dict) -> tuple:
        """
        检查 HTTP 响应是否匹配指纹模式

        :param http_check: http_check 配置字典
        :param resp: HTTP 响应字典
        :return: (status_match, matched, missed)
        """
        expected_codes = http_check.get('status_codes', [200])
        status_match = resp['status_code'] in expected_codes

        fingerprints = http_check.get('fingerprints', [])
        matched = []
        missed = []

        for f in fingerprints:
            pattern = f['pattern']
            if f['type'] == 'body':
                if pattern in resp.get('body', ''):
                    matched.append(pattern)
                else:
                    missed.append(pattern)
            elif f['type'] == 'header':
                header_val = next(
                    (v for k, v in resp.get('headers', {}).items()
                     if k.lower() == pattern.lower()),
                    None
                )
                if header_val:
                    matched.append(pattern)
                else:
                    missed.append(pattern)

        return (status_match, matched, missed)

    @staticmethod
    def _judge(fp: dict, status_match: bool, matched: list, missed: list) -> str:
        """
        判定风险等级

        :param fp: 指纹字典
        :param status_match: HTTP 状态码是否匹配
        :param matched: 匹配的指纹列表
        :param missed: 未匹配的指纹列表
        :return: vulnerable / likely / not_vulnerable
        """
        if not status_match:
            return 'not_vulnerable'

        fingerprints = fp.get('http_check', {}).get('fingerprints', [])
        required = [f for f in fingerprints if f.get('required', False)]
        required_patterns = {f['pattern'] for f in required}

        if required_patterns:
            if required_patterns.issubset(set(matched)):
                return 'vulnerable'
            return 'likely'

        if matched:
            return 'likely'
        return 'likely'

    async def _check_http(self, subdomain: str, fp: dict) -> dict:
        """
        对所有 paths 并行 HTTP 检查，取最高风险

        :param subdomain: 子域名
        :param fp: 指纹字典
        :return: 包含 judgment 字段的结果字典
        """
        http_check = fp.get('http_check', {})
        paths = http_check.get('paths', ['/'])

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._check_http_path(session, subdomain, p, self.http_timeout) for p in paths]
            responses = await asyncio.gather(*tasks)

        best = None
        best_risk = 99
        for i, resp in enumerate(responses):
            if resp.get('error'):
                continue
            status_match, matched, missed = self._check_fingerprint_match(http_check, resp)
            status = self._judge(fp, status_match, matched, missed)
            risk = RISK_ORDER.get(status, 99)
            if risk < best_risk:
                best_risk = risk
                best = {
                    'http_path': paths[i],
                    'http_status': resp['status_code'],
                    'matched_fingerprints': matched,
                    'missed_fingerprints': missed,
                    'judgment': status,
                    'http_error': None,
                }

        if best is None:
            first_error = responses[0].get('error', 'unknown') if responses else 'unknown'
            return {
                'http_path': paths[0],
                'http_status': 0,
                'matched_fingerprints': [],
                'missed_fingerprints': [],
                'judgment': 'unknown',
                'http_error': first_error,
            }

        return best

    async def run(self, subdomains: Set[str], show_progress: bool = True) -> List[TakeoverResult]:
        """
        批量异步检查子域名（带进度条和存活预检）

        流程：
        1. 存活预检（A 记录解析）→ 过滤掉 NXDOMAIN
        2. CNAME 解析 + 指纹匹配
        3. HTTP 确认（对匹配指纹的子域名）

        :param subdomains: 子域名集合
        :param show_progress: 是否显示 tqdm 进度条
        :return: TakeoverResult 列表
        """
        if not subdomains:
            return []

        # ============ 阶段 1：存活预检（A 记录解析）============
        dead_results: List[TakeoverResult] = []
        pending_subdomains = subdomains

        if self.pre_check_enabled:
            alive_set: Set[str] = set()
            dead_count = 0
            timeout_count = 0

            semaphore = asyncio.Semaphore(self.concurrent)

            async def _resolve_a_async(subdomain: str, timeout: float = 15) -> Tuple[str, bool, str]:
                """异步执行 A 记录解析，带超时和重试"""
                loop = asyncio.get_running_loop()
                for attempt in range(2):
                    try:
                        is_alive, reason = await asyncio.wait_for(
                            loop.run_in_executor(
                                None, TakeoverCheck._resolve_a, subdomain
                            ),
                            timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        is_alive, reason = False, 'TIMEOUT'
                    if reason != 'TIMEOUT':
                        return subdomain, is_alive, reason
                    if attempt == 0:
                        await asyncio.sleep(1)
                return subdomain, is_alive, reason

            async def _pre_check_one(subdomain: str) -> Tuple[str, bool, str]:
                async with semaphore:
                    return await _resolve_a_async(subdomain)

            pre_check_tasks = [_pre_check_one(s) for s in subdomains]
            pre_results = await asyncio.gather(*pre_check_tasks)

            for s, is_alive, reason in pre_results:
                if is_alive:
                    alive_set.add(s)
                elif reason == 'TIMEOUT':
                    # 超时不确定，仍纳入检测
                    alive_set.add(s)
                    timeout_count += 1
                else:
                    # NXDOMAIN / ERROR → 记录为 dead，跳过 CNAME 检测
                    dead_results.append(TakeoverResult(
                        subdomain=s, status='not_vulnerable',
                        detail={'dns_status': reason, 'cname_matched': None,
                                'pre_check': 'dead'}
                    ))
                    dead_count += 1

            pending_subdomains = alive_set
            logger.info(
                f'存活预检完成: {len(alive_set)} 存活 (含 {timeout_count} 超时), '
                f'{dead_count} 已死 → 跳过接管检测'
            )

            if not pending_subdomains:
                return dead_results

        # ============ 阶段 2：CNAME 接管检测 ============
        semaphore = asyncio.Semaphore(self.concurrent)

        async def _resolve_cname_async(subdomain: str, timeout: float = 25) -> Tuple[Optional[str], str]:
            """异步执行 DNS 解析，带超时控制。TIMEOUT 时重试一次。"""
            loop = asyncio.get_running_loop()
            for attempt in range(2):
                try:
                    cname, status = await asyncio.wait_for(
                        loop.run_in_executor(
                            None, TakeoverCheck._resolve_cname, subdomain
                        ),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    cname, status = None, 'TIMEOUT'
                if status != 'TIMEOUT':
                    return cname, status
                if attempt == 0:
                    await asyncio.sleep(2)
            return cname, status

        async def _check_one(subdomain: str) -> TakeoverResult:
            async with semaphore:
                cname, dns_status = await _resolve_cname_async(subdomain)

                result = self._process_dns_result(subdomain, cname, dns_status)
                if result.status in ('error', 'not_vulnerable'):
                    return result
                fp = self.fingerprints.get(result.service)
                if not fp:
                    return result
                return await self._apply_http_check(result, fp)

        tasks = [_check_one(s) for s in pending_subdomains]
        results: List[TakeoverResult] = []

        pbar = None
        if show_progress:
            pbar = tqdm(
                total=len(tasks),
                desc='CNAME接管检测',
                ncols=60,
                mininterval=0.3,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )

        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            if pbar:
                pbar.update(1)

        if pbar:
            pbar.close()

        # 合并阶段 1（预检已死）和阶段 2（CNAME 接管检测）的结果
        return dead_results + results


def takeover_run(domain: str, subdomains: Set[str],
                 config: Optional[dict] = None) -> List[dict]:
    """
    模块级入口（同步）

    :param domain: 目标域名
    :param subdomains: 子域名集合
    :param config: 可选配置（支持 show_progress 键控制进度条）
    :return: 字典列表
    """
    show_progress = (config or {}).get('show_progress', True)
    check = TakeoverCheck(domain, config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(check.run(subdomains, show_progress))
        return [{
            'subdomain': r.subdomain,
            'cname': r.cname,
            'service': r.service,
            'severity': r.severity,
            'status': r.status,
            'detail': r.detail,
        } for r in results]
    finally:
        loop.close()
