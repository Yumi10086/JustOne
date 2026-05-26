"""
CDN 识别模块

通过 CNAME 关键字匹配和 IP CIDR 地址段两种方式，
识别子域名是否使用了 CDN 服务。
"""

import json
import ipaddress
from pathlib import Path
from typing import Optional, Set, Dict, Any, List, Tuple

import dns.resolver

from common.module import Module
from common import utils
from common import resolve
from config.logging import logger


class CDNCheck(Module):
    """
    CDN 识别模块

    支持检测方式:
    - CNAME 关键字匹配: 检查 DNS CNAME 记录是否包含已知 CDN 特征
    - IP CIDR 匹配: 检查解析 IP 是否落在已知 CDN 地址段内
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 CDN 检查模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'CDNCheck'
        self.source = 'cdn_check'
        self.cdn_cnames: Dict[str, str] = {}
        self.cdn_ip_ranges: List[ipaddress.IPv4Network] = []
        self._load_cdn_data()

    def _load_cdn_data(self):
        """加载 CDN 特征数据"""
        data_dir = Path(__file__).parent.parent.parent / 'data'

        cname_file = data_dir / 'cdn_cname_keywords.json'
        if cname_file.exists():
            with open(cname_file, 'r', encoding='utf-8') as f:
                self.cdn_cnames = json.load(f)
            logger.debug(f'加载 {len(self.cdn_cnames)} 条 CDN CNAME 特征')

        cidr_file = data_dir / 'cdn_ip_cidr.json'
        if cidr_file.exists():
            with open(cidr_file, 'r', encoding='utf-8') as f:
                cidrs = json.load(f)
            for cidr in cidrs:
                try:
                    self.cdn_ip_ranges.append(ipaddress.ip_network(cidr))
                except ValueError:
                    continue
            logger.debug(f'加载 {len(self.cdn_ip_ranges)} 条 CDN IP CIDR 特征')

    def _check_cname(self, subdomain: str) -> Tuple[bool, Optional[str]]:
        """
        通过 CNAME 记录判断是否使用 CDN

        :param str subdomain: 子域名
        :return: (是否CDN, CDN提供商)
        """
        try:
            resolver_obj = utils.dns_resolver()
            answers = resolver_obj.resolve(subdomain, 'CNAME')
            cname = str(answers[0]).rstrip('.')
            for keyword, provider in self.cdn_cnames.items():
                if keyword in cname:
                    return True, provider
        except Exception:
            pass
        return False, None

    def _check_ip_cidr(self, ip: str) -> bool:
        """
        通过 IP CIDR 地址段判断是否使用 CDN

        :param str ip: IP 地址
        :return: 是否落在 CDN 地址段内
        """
        try:
            addr = ipaddress.ip_address(ip.strip())
            for network in self.cdn_ip_ranges:
                if addr in network:
                    return True
        except ValueError:
            pass
        return False

    def check(self, subdomain: str) -> Dict[str, Any]:
        """
        检查单个子域名是否使用 CDN

        :param str subdomain: 子域名
        :return: CDN 检测结果字典
        """
        result = {
            'subdomain': subdomain,
            'cdn': 0,
            'cdn_provider': '',
        }

        is_cdn, provider = self._check_cname(subdomain)
        if is_cdn:
            result['cdn'] = 1
            result['cdn_provider'] = provider
            return result

        info = resolve.resolve_domain(subdomain)
        if info and info.get('ip'):
            ip = info['ip'].split(',')[0]
            if self._check_ip_cidr(ip):
                result['cdn'] = 1

        return result

    def run(self, subdomains: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """
        执行 CDN 识别

        :param Set[str] subdomains: 要检查的子域名集合，默认使用 self.subdomains
        :return: CDN 检测结果列表
        """
        target = set(subdomains) if subdomains else self.subdomains
        if not target:
            logger.warning('CDN 识别无输入子域名')
            return []

        self.subdomains = target
        self.begin()

        results = []
        for s in sorted(target):
            r = self.check(s)
            results.append(r)
            if r['cdn']:
                self.infos[s] = r

        logger.info(f'CDN 识别完成: {sum(1 for r in results if r["cdn"])}/{len(results)} 使用 CDN')

        self.finish()
        return results


def run(domain: str, config: Optional[dict] = None) -> list:
    """
    模块执行入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: CDN 检测结果列表
    """
    module = CDNCheck(domain, config)
    return module.run()
