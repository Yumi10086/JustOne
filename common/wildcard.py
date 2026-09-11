# -*- coding: utf-8 -*-
"""
泛解析（Wildcard DNS）检测与过滤模块

泛解析指 *.域名 对任意子域名均返回解析结果，会使子域爆破/置换/收集产生大量
假阳性。本模块统一封装检测与过滤能力，供 brute / altdns / collect 复用。

设计要点:
    - 多随机标签探测：生成 N 个随机标签，任一解析成功即判定存在泛解析，
      并汇总所有观测的 IP / CNAME（应对轮询返回不同 IP 的场景）。
    - 记录类型：A 记录（经 common.resolve.resolve_domain）+ CNAME；
      仅当 A 为空时补查 AAAA，避免为每个候选额外查询带来的性能损耗。
    - 匹配语义：候选的所有 IP 均落在泛解析 IP 集合（可选同 /24 网段）内，
      或候选 CNAME 命中泛解析 CNAME 集合，则判定为泛解析。
    - WildcardInfo 为只读数据，可跨线程安全使用。
"""

import ipaddress
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

import dns.resolver

from config.logging import logger
from common import resolve

DEFAULT_PROBES = 3
_LABEL_PREFIX = '_wc'


def _split_addr(value) -> Set[str]:
    """
    将解析字段归一化为字符串集合

    :param value: 原始字段，支持逗号分隔字符串、列表/元组/集合或 None
    :return: 去空白后的字符串集合
    """
    if not value:
        return set()
    if isinstance(value, str):
        parts = value.split(',')
    elif isinstance(value, (list, tuple, set, frozenset)):
        parts = list(value)
    else:
        parts = [value]
    result = set()
    for part in parts:
        text = str(part).strip()
        if text:
            result.add(text)
    return result


def parse_record(info: Optional[Dict]) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    解析 resolve.resolve_domain 返回的结果字典

    :param dict info: 解析结果字典
    :return: (IPv4 集合, IPv6 集合, CNAME 集合)
    """
    if not info:
        return set(), set(), set()
    return (
        _split_addr(info.get('ip')),
        _split_addr(info.get('ipv6')),
        _split_addr(info.get('cname')),
    )


def _resolve_aaaa(subdomain: str, nameservers: Optional[List[str]] = None) -> Set[str]:
    """
    查询 AAAA 记录（仅用于泛解析探测与 A 为空的候选）

    :param str subdomain: 子域名
    :param list nameservers: DNS 服务器列表
    :return: IPv6 地址集合
    """
    resolver = dns.resolver.Resolver()
    resolver.nameservers = nameservers or resolve.resolve_config.get('dns_nameservers')
    resolver.timeout = 5
    resolver.lifetime = 10
    try:
        answer = resolver.resolve(subdomain, 'AAAA', tcp=resolve.is_socks5_dns_enabled())
        return {str(rdata) for rdata in answer}
    except Exception:
        return set()


def _resolve_record(subdomain: str, nameservers: Optional[List[str]] = None) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    解析子域名，A 为空时补查 AAAA

    :param str subdomain: 子域名
    :param list nameservers: DNS 服务器列表
    :return: (IPv4 集合, IPv6 集合, CNAME 集合)
    """
    info = resolve.resolve_domain(subdomain, nameservers)
    ipv4, ipv6, cnames = parse_record(info)
    if not ipv4 and not cnames:
        ipv6 = _resolve_aaaa(subdomain, nameservers)
    return ipv4, ipv6, cnames


@dataclass
class WildcardInfo:
    """泛解析检测结果（只读）"""

    domain: str
    detected: bool = False
    ips: Set[str] = field(default_factory=set)
    ipv6s: Set[str] = field(default_factory=set)
    cnames: Set[str] = field(default_factory=set)
    # 轮换 IP 泛解析自动推导的网段（CIDR 字符串），如 {"1.2.3.0/24"}
    networks: Set[str] = field(default_factory=set)
    probes: List[str] = field(default_factory=list)

    def _same_v4_network(self, ip: str) -> bool:
        """判断 IPv4 是否与任一泛解析 IP 处于同一 /24 网段"""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if addr.version != 4:
            return False
        for wildcard_ip in self.ips:
            try:
                waddr = ipaddress.ip_address(wildcard_ip)
            except ValueError:
                continue
            if waddr.version != 4:
                continue
            if addr in ipaddress.ip_network(f'{wildcard_ip}/24', strict=False):
                return True
        return False

    def _in_networks(self, ip: str) -> bool:
        """判断 IPv4 是否落在已推导的泛解析网段内"""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if addr.version != 4:
            return False
        for network in self.networks:
            try:
                if addr in ipaddress.ip_network(network, strict=False):
                    return True
            except ValueError:
                continue
        return False

    def merge(self, other: Optional['WildcardInfo']) -> 'WildcardInfo':
        """
        合并另一个泛解析结果（取并集），返回新对象

        :param WildcardInfo other: 待合并的泛解析结果
        :return: 合并后的泛解析结果
        """
        if not other:
            return self
        return WildcardInfo(
            domain=self.domain,
            detected=self.detected or other.detected,
            ips=set(self.ips) | set(other.ips),
            ipv6s=set(self.ipv6s) | set(other.ipv6s),
            cnames=set(self.cnames) | set(other.cnames),
            networks=set(self.networks) | set(other.networks),
            probes=list(self.probes) + list(other.probes),
        )

    def matches(self, ipv4: Set[str], ipv6: Set[str], cnames: Set[str],
                include_cidr: bool = False) -> bool:
        """
        判断一组解析结果是否属于泛解析

        :param Set[str] ipv4: 候选 IPv4 集合
        :param Set[str] ipv6: 候选 IPv6 集合
        :param Set[str] cnames: 候选 CNAME 集合
        :param bool include_cidr: 是否启用同 /24 网段匹配
        :return: 是否判定为泛解析
        """
        if not self.detected:
            return False
        if cnames and self.cnames and (cnames & self.cnames):
            return True
        if ipv4:
            for ip in ipv4:
                if ip in self.ips:
                    continue
                # 轮换 IP 泛解析：探测到多个不同 IP 时自动按网段匹配
                if self._in_networks(ip):
                    continue
                if include_cidr and self._same_v4_network(ip):
                    continue
                return False
            return True
        if ipv6:
            return ipv6 <= self.ipv6s
        return False

    def matches_record(self, info: Optional[Dict], include_cidr: bool = False) -> bool:
        """
        判断 resolve.resolve_domain 的结果是否属于泛解析

        :param dict info: 解析结果字典
        :param bool include_cidr: 是否启用同 /24 网段匹配
        :return: 是否判定为泛解析
        """
        ipv4, ipv6, cnames = parse_record(info)
        return self.matches(ipv4, ipv6, cnames, include_cidr)


def detect_wildcard(domain: str, probes: int = DEFAULT_PROBES,
                    nameservers: Optional[List[str]] = None) -> WildcardInfo:
    """
    多随机标签探测泛解析

    :param str domain: 目标注册域名
    :param int probes: 随机标签探测次数
    :param list nameservers: DNS 服务器列表
    :return: 泛解析检测结果
    """
    info = WildcardInfo(domain=domain)
    probe_count = max(1, int(probes))
    for _ in range(probe_count):
        label = f'{_LABEL_PREFIX}{uuid.uuid4().hex[:10]}.{domain}'
        ipv4, ipv6, cnames = _resolve_record(label, nameservers)
        if ipv4 or ipv6 or cnames:
            info.detected = True
            info.probes.append(label)
            info.ips |= ipv4
            info.ipv6s |= ipv6
            info.cnames |= cnames
    if info.detected:
        # 轮换 IP 泛解析：探测到多个不同 IPv4 时，自动按 /24 网段匹配，减少漏过滤
        if len(info.ips) >= 2:
            info.networks = {f'{ip}/24' for ip in info.ips}
            logger.warning(
                f'泛解析返回轮换 IP，已启用网段匹配: {sorted(info.networks)}'
            )
        logger.warning(
            f'检测到泛解析: {domain} — IP={sorted(info.ips)} CNAME={sorted(info.cnames)}'
        )
    else:
        logger.debug(f'未检测到泛解析: {domain}')
    return info


def is_wildcard_subdomain(subdomain: str, info: WildcardInfo,
                          nameservers: Optional[List[str]] = None,
                          include_cidr: bool = False) -> bool:
    """
    判断单个子域名是否属于泛解析

    :param str subdomain: 子域名
    :param WildcardInfo info: 泛解析检测结果
    :param list nameservers: DNS 服务器列表
    :param bool include_cidr: 是否启用同 /24 网段匹配
    :return: 是否判定为泛解析
    """
    if not info or not info.detected:
        return False
    ipv4, ipv6, cnames = _resolve_record(subdomain, nameservers)
    return info.matches(ipv4, ipv6, cnames, include_cidr)


def detect_and_filter(subdomains, domain: str,
                      probes: int = DEFAULT_PROBES,
                      nameservers: Optional[List[str]] = None,
                      concurrent: int = 50,
                      include_cidr: bool = False
                      ) -> Tuple[Set[str], Set[str], WildcardInfo]:
    """
    先检测泛解析，若存在则排除全部泛解析子域名

    :param subdomains: 候选子域名集合/列表
    :param str domain: 目标注册域名
    :param int probes: 泛解析探测次数
    :param list nameservers: DNS 服务器列表
    :param int concurrent: 过滤并发数
    :param bool include_cidr: 是否启用同 /24 网段匹配
    :return: (保留的子域名集合, 被移除的泛解析子域名集合, 泛解析检测结果)
    """
    info = detect_wildcard(domain, probes=probes, nameservers=nameservers)
    if not info.detected:
        return {s for s in subdomains if s}, set(), info
    kept, removed = filter_subdomains(
        subdomains, info,
        nameservers=nameservers,
        concurrent=concurrent,
        include_cidr=include_cidr,
    )
    return kept, removed, info


def filter_subdomains(subdomains, info: WildcardInfo,
                      nameservers: Optional[List[str]] = None,
                      concurrent: int = 50,
                      include_cidr: bool = False,
                      progress_callback: Optional[Callable[[int, int], None]] = None
                      ) -> Tuple[Set[str], Set[str]]:
    """
    并发解析并分离泛解析子域名

    :param subdomains: 待过滤的子域名集合/列表
    :param WildcardInfo info: 泛解析检测结果
    :param list nameservers: DNS 服务器列表
    :param int concurrent: 并发数
    :param bool include_cidr: 是否启用同 /24 网段匹配
    :param callable progress_callback: 进度回调 (已完成, 总数)
    :return: (保留的子域名集合, 被移除的泛解析子域名集合)
    """
    candidates = [s for s in subdomains if s]
    total = len(candidates)
    if not info or not info.detected or total == 0:
        return set(candidates), set()

    removed: Set[str] = set()
    kept: Set[str] = set()
    workers = max(1, min(concurrent, total))

    def worker(subdomain: str) -> Tuple[str, bool]:
        ipv4, ipv6, cnames = _resolve_record(subdomain, nameservers)
        return subdomain, info.matches(ipv4, ipv6, cnames, include_cidr)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(worker, s): s for s in candidates}
        done = 0
        for future in as_completed(futures):
            subdomain, wild = future.result()
            if wild:
                removed.add(subdomain)
            else:
                kept.add(subdomain)
            done += 1
            if progress_callback:
                progress_callback(done, total)

    logger.info(f'泛解析过滤: 检查 {total} 个，移除 {len(removed)} 个，保留 {len(kept)} 个')
    return kept, removed
