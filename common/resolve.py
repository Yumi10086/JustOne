"""
DNS 解析模块
"""

import json
import random
import socket as socket_module
from pathlib import Path
from typing import List, Dict, Optional, Callable
from urllib.parse import urlparse

import dns.exception
import dns.query
import dns.resolver

from config.logging import logger

# ==================== SOCKS5 DNS 代理 ====================

_socks5_enabled = False
_socks5_proxies: List[tuple] = []  # [(host, port), ...]

# 保存 dnspython 原始函数，用于恢复
_orig_tcp = dns.query.tcp

resolve_config = {
    'project_root': Path(__file__).parent.parent,
    'results_dir': Path(__file__).parent.parent / 'results',
    'dns_nameservers': ['223.5.5.5', '119.29.29.29', '114.114.114.114', '8.8.8.8', '1.1.1.1'],
}


_socks5_fallback_warned = False


def _warn_socks5_fallback():
    """SOCKS5 代理不可用时，仅警告一次"""
    global _socks5_fallback_warned
    if not _socks5_fallback_warned:
        _socks5_fallback_warned = True
        logger.warning('SOCKS5 DNS 代理不可用，已自动回退直连 DNS')


def _socks5_tcp(q, where, timeout=None, port=53, source=None, source_port=0,
                one_rr_per_rrset=False, ignore_trailing=False, sock=None):
    """
    SOCKS5 代理版 dns.query.tcp（代理优先，失败回退直连）

    先尝试通过 SOCKS5 代理连接 DNS 服务器进行 DNS-over-TCP 查询，
    如果代理不可用（连接超时/拒绝），自动回退到直连 DNS。
    回退仅警告一次，避免日志刷屏。

    :param q: dns.message.Message，要发送的 DNS 查询
    :param where: str，DNS 服务器地址
    :param timeout: float，超时秒数
    :param port: int，端口
    :return: dns.message.Message，DNS 响应
    """
    import socks as _socks
    import dns.message
    import struct

    proxy_addr = random.choice(_socks5_proxies)

    s = _socks.socksocket(socket_module.AF_INET, socket_module.SOCK_STREAM)
    s.set_proxy(_socks.SOCKS5, proxy_addr[0], proxy_addr[1], rdns=True)
    if timeout:
        s.settimeout(timeout)

    try:
        # SOCKS5 握手 + CONNECT 到 DNS 服务器
        s.connect((where, port))

        # DNS-over-TCP: 2 字节长度前缀 + DNS 报文
        wire = q.to_wire()
        s.sendall(struct.pack('!H', len(wire)) + wire)

        # 接收响应长度
        resp_len_data = s.recv(2)
        resp_len = struct.unpack('!H', resp_len_data)[0]

        # 接收响应
        resp_data = b''
        while len(resp_data) < resp_len:
            chunk = s.recv(resp_len - len(resp_data))
            if not chunk:
                break
            resp_data += chunk

        return dns.message.from_wire(resp_data, one_rr_per_rrset=one_rr_per_rrset,
                                     ignore_trailing=ignore_trailing,
                                     keyring=q.keyring)

    except (OSError, _socks.ProxyConnectionError, _socks.GeneralProxyError):
        # 代理不可用（超时/拒绝/未运行），回退直连 DNS
        _warn_socks5_fallback()
        return _orig_tcp(q, where, timeout=timeout, port=port,
                         source=source, source_port=source_port,
                         one_rr_per_rrset=one_rr_per_rrset,
                         ignore_trailing=ignore_trailing)

    finally:
        s.close()


def init_dns_proxy(proxy_pool: list = None):
    """
    初始化 SOCKS5 DNS 代理

    替换 dns.query.tcp 为 SOCKS5 代理版本。
    SOCKS5 UDP ASSOCIATE 在不同实现中不可靠，因此强制 TCP 模式。

    :param list proxy_pool: 代理池列表（含 socks5:// 或 socks5h:// 前缀的地址）
    """
    global _socks5_enabled, _socks5_proxies

    if not proxy_pool:
        _socks5_enabled = False
        _socks5_proxies = []
        dns.query.tcp = _orig_tcp
        logger.debug('DNS 代理未启用（代理池为空）')
        return

    socks5_list = []
    for addr in proxy_pool:
        if isinstance(addr, str) and addr.strip():
            addr = addr.strip()
            if addr.startswith('socks5://') or addr.startswith('socks5h://'):
                parsed = urlparse(addr)
                hostname = parsed.hostname
                port = parsed.port or 1080
                if hostname:
                    socks5_list.append((hostname, port))

    if not socks5_list:
        _socks5_enabled = False
        _socks5_proxies = []
        dns.query.tcp = _orig_tcp
        logger.debug('DNS 代理未启用（未配置 SOCKS5 代理）')
        return

    _socks5_enabled = True
    _socks5_proxies = socks5_list
    dns.query.tcp = _socks5_tcp
    logger.info(f'DNS SOCKS5 代理已启用: {len(socks5_list)} 个代理，强制 TCP 模式')


def is_socks5_dns_enabled() -> bool:
    """
    检查是否已启用 SOCKS5 DNS 代理

    :return: 是否启用
    """
    return _socks5_enabled


def set_resolve_config(config: dict):
    """设置全局解析配置"""
    resolve_config.update(config)


def filter_subdomain(data):
    """
    过滤出没有 IP 的子域

    :param list data: 待过滤的数据列表
    :return: 待解析的子域列表
    """
    logger.debug('正在过滤需要解析的子域名')
    subdomains = []
    for infos in data:
        if not infos.get('ip'):
            subdomain = infos.get('subdomain')
            if subdomain:
                subdomains.append(subdomain)
    return subdomains


def update_data(data, infos):
    """
    更新解析结果

    :param list data: 待更新的数据列表
    :param dict infos: 子域解析信息
    :return: 更新后的数据列表
    """
    logger.debug('正在更新解析结果')
    if not infos:
        logger.warning('没有有效的解析结果')
        return data
    new_data = list()
    for items in data:
        if items.get('ip'):
            new_data.append(items)
            continue
        subdomain = items.get('subdomain')
        record = infos.get(subdomain)
        if record:
            items.update(record)
            new_data.append(items)
        else:
            logger.debug(f'{subdomain} 解析无结果')
    return new_data


def resolve_domain(subdomain: str, nameservers: List[str] = None) -> Optional[Dict]:
    """
    解析单个域名

    :param str subdomain: 要解析的子域名
    :param list nameservers: DNS 服务器列表
    :return: 解析信息字典，解析失败返回 None
    """
    info = {'subdomain': subdomain, 'resolve': 0, 'alive': 0}
    ns = nameservers or resolve_config.get('dns_nameservers')

    resolver = dns.resolver.Resolver()
    resolver.nameservers = ns
    resolver.timeout = 5
    resolver.lifetime = 10

    try:
        # SOCKS5 必须使用 TCP 模式（UDP ASSOCIATE 在不同实现中不可靠）
        a_records = resolver.resolve(subdomain, 'A', tcp=_socks5_enabled)
        ips = [str(rdata) for rdata in a_records]
        info['resolve'] = 1
        info['alive'] = 1
        info['ip'] = ','.join(ips)
        info['reason'] = 'OK'

        try:
            cname_records = resolver.resolve(subdomain, 'CNAME', tcp=_socks5_enabled)
            cnames = [str(rdata) for rdata in cname_records]
            info['cname'] = ','.join(cnames)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            pass

        return info

    except dns.resolver.NXDOMAIN:
        info['reason'] = 'NXDOMAIN'
        return info
    except dns.resolver.NoAnswer:
        info['reason'] = 'NoAnswer'
        return info
    except dns.exception.Timeout:
        info['reason'] = 'Timeout'
        return info
    except Exception as e:
        logger.debug(f'解析 {subdomain} 时出错: {e}')
        info['reason'] = f'错误: {type(e).__name__}'
        return info


def resolve_batch(subdomains: List[str],
                  nameservers: List[str] = None,
                  progress_callback: Callable = None) -> Dict[str, Dict]:
    """
    批量解析子域名

    :param list subdomains: 要解析的子域名列表
    :param list nameservers: DNS 服务器列表
    :param callable progress_callback: 进度回调函数
    :return: 子域名 -> 解析信息 的字典
    """
    results = {}
    total = len(subdomains)

    for i, subdomain in enumerate(subdomains):
        if progress_callback:
            progress_callback(i + 1, total)

        info = resolve_domain(subdomain, nameservers)
        if info:
            results[subdomain] = info

    return results


def run_resolve(domain: str, data: List[Dict], config: dict = None) -> List[Dict]:
    """
    使用 dnspython 解析子域名（无需 massdns）

    :param str domain: 主域名
    :param list data: 子域名数据列表，包含 'subdomain' 键
    :param dict config: 可选配置字典
    :return: 解析后的数据列表
    """
    cfg = config or {}
    nameservers = cfg.get('nameservers', resolve_config.get('dns_nameservers'))
    progress_callback = cfg.get('progress_callback')

    logger.info(f'开始解析域名 {domain} 的子域名')
    subdomains = filter_subdomain(data)

    if not subdomains:
        logger.info('没有需要解析的子域名')
        return data

    logger.info(f'正在解析 {len(subdomains)} 个子域名')
    infos = resolve_batch(subdomains, nameservers, progress_callback)

    data = update_data(data, infos)
    logger.info(f'完成域名 {domain} 的子域名解析')
    return data