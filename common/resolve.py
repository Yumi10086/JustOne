"""
DNS 解析模块
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Callable

import dns.exception
import dns.resolver

from config.logging import logger

resolve_config = {
    'project_root': Path(__file__).parent.parent,
    'results_dir': Path(__file__).parent.parent / 'results',
    'dns_nameservers': ['223.5.5.5', '119.29.29.29', '114.114.114.114', '8.8.8.8', '1.1.1.1'],
}


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
        a_records = resolver.resolve(subdomain, 'A')
        ips = [str(rdata) for rdata in a_records]
        info['resolve'] = 1
        info['alive'] = 1
        info['ip'] = ','.join(ips)
        info['reason'] = 'OK'

        try:
            cname_records = resolver.resolve(subdomain, 'CNAME')
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