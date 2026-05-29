"""
DNS 安全检测模块
检测 DNSSEC 状态、多解析器一致性（投毒/劫持）、缓存污染风险
"""

from typing import Optional, Dict, List, Any, Set
from dataclasses import dataclass, asdict, field

import dns.resolver
import dns.rdatatype
import dns.exception

from common.module import Module
from config.logging import logger

DOMESTIC_NS = ['223.5.5.5', '114.114.114.114']
INTERNATIONAL_NS = ['8.8.8.8', '1.1.1.1']
ALL_NS = list(dict.fromkeys(DOMESTIC_NS + INTERNATIONAL_NS))


@dataclass
class DNSSecurityResult:
    check: str
    status: str  # secure / insecure / suspicious / error / info
    detail: str
    extra: Optional[Dict[str, Any]] = None


class DNSSecurityCheck(Module):
    def __init__(self, domain: str, config: Optional[dict] = None):
        super().__init__(domain, config)
        self.module = 'DNSSecurityCheck'
        self.source = 'dns_security'
        self.results: List[DNSSecurityResult] = []

    def _make_resolver(self, nameservers: List[str]) -> dns.resolver.Resolver:
        r = dns.resolver.Resolver()
        r.nameservers = nameservers
        r.timeout = 5
        r.lifetime = 10
        return r

    def _query(self, qname: str, rdtype: str, nameservers: List[str] = None) -> Optional[List[str]]:
        ns = nameservers or ALL_NS
        resolver = self._make_resolver(ns)
        try:
            answers = resolver.resolve(qname, rdtype, raise_on_no_answer=False)
            return [str(r) for r in answers]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
            return None

    def check_dnssec(self) -> DNSSecurityResult:
        try:
            resolver = self._make_resolver(ALL_NS)

            ds_records = []
            try:
                ds_answers = resolver.resolve(self.domain, 'DS', raise_on_no_answer=False)
                ds_records = [str(r) for r in ds_answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
                pass

            rrsig_records = []
            try:
                rrsig_answers = resolver.resolve(self.domain, 'RRSIG', raise_on_no_answer=False)
                rrsig_records = [str(r) for r in rrsig_answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
                pass

            nsec_records = []
            try:
                nsec_answers = resolver.resolve(self.domain, 'NSEC', raise_on_no_answer=False)
                nsec_records = [str(r) for r in nsec_answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
                pass

            has_ds = len(ds_records) > 0
            has_rrsig = len(rrsig_records) > 0
            has_nsec = len(nsec_records) > 0

            if has_ds and has_rrsig:
                return DNSSecurityResult(
                    check='DNSSEC',
                    status='secure',
                    detail='域名的 DNSSEC 配置完整（DS + RRSIG）',
                    extra={'ds_count': len(ds_records), 'rrsig_count': len(rrsig_records)},
                )
            elif has_ds:
                return DNSSecurityResult(
                    check='DNSSEC',
                    status='insecure',
                    detail='存在 DS 记录但无 RRSIG，DNSSEC 配置不完整',
                    extra={'ds_count': len(ds_records)},
                )
            elif has_nsec:
                return DNSSecurityResult(
                    check='DNSSEC',
                    status='info',
                    detail='未启用 DNSSEC，存在 NSEC 记录',
                    extra={'nsec_count': len(nsec_records)},
                )
            else:
                return DNSSecurityResult(
                    check='DNSSEC',
                    status='info',
                    detail='未启用 DNSSEC',
                )
        except Exception as e:
            return DNSSecurityResult(
                check='DNSSEC',
                status='error',
                detail=f'DNSSEC 检测失败: {e}',
            )

    def check_consistency(self) -> DNSSecurityResult:
        try:
            domestic = self._query(self.domain, 'A', DOMESTIC_NS)
            international = self._query(self.domain, 'A', INTERNATIONAL_NS)

            domestic_set = set(domestic or [])
            intl_set = set(international or [])

            both = domestic_set & intl_set
            only_domestic = domestic_set - intl_set
            only_intl = intl_set - domestic_set

            if not domestic and not international:
                return DNSSecurityResult(
                    check='解析一致性',
                    status='error',
                    detail='国内与国外 DNS 均无法解析',
                )

            if only_domestic or only_intl:
                diff_detail = []
                if only_domestic:
                    diff_detail.append(f'国内独有: {",".join(only_domestic)}')
                if only_intl:
                    diff_detail.append(f'国外独有: {",".join(only_intl)}')
                return DNSSecurityResult(
                    check='解析一致性',
                    status='suspicious',
                    detail=f'检测到解析结果差异（可能受 GFW 污染或 DNS 劫持）: {"；".join(diff_detail)}',
                    extra={
                        'domestic': sorted(domestic_set) if domestic_set else None,
                        'international': sorted(intl_set) if intl_set else None,
                        'common': sorted(both) if both else None,
                    },
                )

            return DNSSecurityResult(
                check='解析一致性',
                status='secure',
                detail=f'国内与国外解析结果一致: {",".join(domestic_set) if domestic_set else "无记录"}',
                extra={
                    'ip': sorted(domestic_set) if domestic_set else None,
                },
            )
        except Exception as e:
            return DNSSecurityResult(
                check='解析一致性',
                status='error',
                detail=f'一致性检测失败: {e}',
            )

    def check_hijack(self) -> DNSSecurityResult:
        try:
            resolver = self._make_resolver(ALL_NS)

            ns_records = []
            try:
                ns_answers = resolver.resolve(self.domain, 'NS', raise_on_no_answer=False)
                ns_records = [str(r) for r in ns_answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
                pass

            soa_records = []
            try:
                soa_answers = resolver.resolve(self.domain, 'SOA', raise_on_no_answer=False)
                soa_records = [str(r) for r in soa_answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
                pass

            extra = {}
            if ns_records:
                extra['ns_servers'] = ns_records
            if soa_records:
                extra['soa'] = soa_records

            resolver_checks = {
                'domestic': self._make_resolver(DOMESTIC_NS),
                'international': self._make_resolver(INTERNATIONAL_NS),
            }

            hijack_flags = []
            for name, r in resolver_checks.items():
                try:
                    r.resolve(self.domain, 'A')
                except dns.resolver.NXDOMAIN:
                    hijack_flags.append(f'{name} 返回 NXDOMAIN（其它解析器有IP）')
                except Exception:
                    pass

            if not ns_records:
                return DNSSecurityResult(
                    check='劫持检测',
                    status='info',
                    detail='无法获取 NS 记录',
                    extra=extra or None,
                )

            return DNSSecurityResult(
                check='劫持检测',
                status='secure' if not hijack_flags else 'suspicious',
                detail='未检测到劫持迹象' if not hijack_flags else '; '.join(hijack_flags),
                extra=extra or None,
            )
        except Exception as e:
            return DNSSecurityResult(
                check='劫持检测',
                status='error',
                detail=f'劫持检测异常: {e}',
            )

    def run(self, subdomains: Set[str] = None) -> List[DNSSecurityResult]:
        self.begin()
        self.results = [
            self.check_dnssec(),
            self.check_consistency(),
            self.check_hijack(),
        ]
        self.finish()
        return self.results


def run(domain: str, config: Optional[dict] = None) -> List[DNSSecurityResult]:
    module = DNSSecurityCheck(domain, config)
    return module.run()
