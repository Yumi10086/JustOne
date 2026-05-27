# -*- coding: utf-8 -*-
"""
子域名接管检测主模块

负责 DNS CNAME 查询、指纹匹配和 HTTP 确认的编排。
"""

import asyncio
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, Set, List, Tuple

import dns.resolver

from modules.takeover.fingerprints import load_fingerprints, find_matching_fingerprint


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
        :param config: 可选配置（fingerprint_file, concurrent, http_timeout）
        """
        self.domain = domain
        self.config = config or {}
        self.fingerprints = load_fingerprints(
            self.config.get('fingerprint_file')
        )
        self.concurrent = self.config.get('concurrent', 20)
        self.http_timeout = self.config.get('http_timeout', 10)

    @lru_cache(maxsize=1024)
    def _resolve_cname(self, subdomain: str) -> Tuple[Optional[str], str]:
        """
        同步 DNS CNAME 查询（带 lru_cache）

        :param subdomain: 子域名
        :return: (cname_target, dns_status)
                 dns_status: NOERROR / NXDOMAIN / TIMEOUT / ERROR:msg
        """
        try:
            answers = dns.resolver.resolve(subdomain, 'CNAME')
            return (str(answers[0].target), 'NOERROR')
        except dns.resolver.NoAnswer:
            return (None, 'NOERROR')
        except dns.resolver.NXDOMAIN:
            return (None, 'NXDOMAIN')
        except dns.resolver.Timeout:
            return (None, 'TIMEOUT')
        except Exception as e:
            return (None, f'ERROR:{e}')

    def check_subdomain(self, subdomain: str) -> TakeoverResult:
        """
        检查单个子域名的接管风险（同步入口）

        :param subdomain: 要检查的子域名
        :return: TakeoverResult
        """
        cname, dns_status = self._resolve_cname(subdomain)

        # DNS 异常处理
        if dns_status in ('TIMEOUT',) or dns_status.startswith('ERROR:'):
            return TakeoverResult(
                subdomain=subdomain,
                cname=cname,
                status='error',
                detail={'dns_status': dns_status, 'cname_matched': None}
            )

        if cname is None:
            return TakeoverResult(
                subdomain=subdomain,
                cname=None,
                status='not_vulnerable',
                detail={'dns_status': dns_status, 'cname_matched': None}
            )

        # CNAME 匹配
        match_result = find_matching_fingerprint(cname, self.fingerprints)
        if match_result is None:
            return TakeoverResult(
                subdomain=subdomain,
                cname=cname,
                status='not_vulnerable',
                detail={'dns_status': dns_status, 'cname_matched': None}
            )

        service_id, fp, matched_pattern = match_result
        result = TakeoverResult(
            subdomain=subdomain,
            cname=cname,
            service=service_id,
            severity=fp.get('severity'),
            detail={
                'dns_status': dns_status,
                'cname_matched': matched_pattern,
            }
        )

        # HTTP 确认阶段 — 需要事件循环
        http_check = fp.get('http_check', {})
        if http_check.get('enabled', True):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            http_result = loop.run_until_complete(self._check_http(subdomain, fp))
            result.detail.update(http_result)
            result.status = http_result.get('judgment', 'unknown')
        else:
            result.status = 'likely'

        return result

    async def _check_http(self, subdomain: str, fp: dict) -> dict:
        """
        HTTP 确认接口（由后续 Task 4 实现完整逻辑，当前返回 unknown）

        :param subdomain: 子域名
        :param fp: 指纹字典
        :return: 包含 judgment 字段的结果字典
        """
        return {
            'http_enabled': True,
            'judgment': 'unknown',
            'http_status': 0,
            'http_path': '/',
            'matched_fingerprints': [],
            'missed_fingerprints': [],
            'http_error': 'not implemented',
        }

    async def run(self, subdomains: Set[str]) -> List[TakeoverResult]:
        """
        批量异步检查子域名

        :param subdomains: 子域名集合
        :return: TakeoverResult 列表
        """
        semaphore = asyncio.Semaphore(self.concurrent)

        async def _check_one(subdomain: str) -> TakeoverResult:
            async with semaphore:
                cname, dns_status = self._resolve_cname(subdomain)

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
                result = TakeoverResult(
                    subdomain=subdomain, cname=cname, service=service_id,
                    severity=fp.get('severity'),
                    detail={'dns_status': dns_status, 'cname_matched': matched_pattern}
                )

                http_check = fp.get('http_check', {})
                if http_check.get('enabled', True):
                    http_result = await self._check_http(subdomain, fp)
                    result.detail.update(http_result)
                    result.status = http_result.get('judgment', 'unknown')
                else:
                    result.status = 'likely'

                return result

        tasks = [_check_one(s) for s in subdomains]
        return list(await asyncio.gather(*tasks))


def takeover_run(domain: str, subdomains: Set[str],
                 config: Optional[dict] = None) -> List[dict]:
    """
    模块级入口（同步）

    :param domain: 目标域名
    :param subdomains: 子域名集合
    :param config: 可选配置
    :return: 字典列表
    """
    check = TakeoverCheck(domain, config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(check.run(subdomains))
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
