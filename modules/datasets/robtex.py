"""
Robtex 子域查询模块

基于 freeapi.robtex.com/pdns 免费 PassiveDNS API。
Robtex 是当前少数仍免费且无需认证的 PassiveDNS 源。
通过正向查询 + IP 反向查询，可发现共享托管环境中的子域名。
"""

import json
import re
import time
from typing import Optional, Set

from common.module import Module
from config.logging import logger


class Robtex(Module):
    """
    Robtex PDNS 子域查询接口

    免费 API 端点：https://freeapi.robtex.com/pdns
    返回格式：NDJSON（每行一个 JSON 对象）
    """

    BASE_URL = 'https://freeapi.robtex.com/pdns'
    IP_RRTYPES = {'A', 'AAAA'}
    REQUEST_DELAY = 1

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 Robtex 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Robtex'
        self.source = 'robtex'
        self._queried_ips: Set[str] = set()

    def _setup_headers(self):
        """设置请求头"""
        self.header = self.get_header()
        self.header.update({
            'Accept': 'application/x-ndjson',
        })

    def _parse_ndjson(self, text: str) -> list:
        """
        安全解析 NDJSON

        :param text: NDJSON 文本
        :return: 解析成功的记录列表
        """
        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.debug(
                    f'{self.source} JSON 解析失败: {e} | 内容: {line[:100]}'
                )
                continue
        return records

    def _query_forward(self) -> list:
        """
        正向查询：获取域名的所有 DNS 记录

        :return: PDNS 记录列表
        """
        url = f'{self.BASE_URL}/forward/{self.domain}'
        resp = self.get(url, check=False)
        if not resp:
            logger.warning(f'{self.source} 正向查询无响应')
            return []
        if resp.status_code == 404:
            logger.info(f'{self.source} 域名 {self.domain} 无记录')
            return []
        if resp.status_code == 429:
            logger.warning(f'{self.source} 频率限制，请降低查询速度')
            return []
        if resp.status_code != 200:
            logger.warning(f'{self.source} 返回状态码 {resp.status_code}')
            return []
        return self._parse_ndjson(resp.text)

    def _query_reverse(self, ip: str) -> list:
        """
        IP 反向查询：获取解析到该 IP 的所有域名

        :param ip: IP 地址
        :return: PDNS 记录列表
        """
        if ip in self._queried_ips:
            return []
        self._queried_ips.add(ip)

        time.sleep(self.REQUEST_DELAY)

        url = f'{self.BASE_URL}/reverse/{ip}'
        resp = self.get(url, check=False)
        if not resp or resp.status_code != 200:
            return []
        return self._parse_ndjson(resp.text)

    def _is_subdomain(self, name: str) -> bool:
        """
        判断域名是否是目标域名的子域

        :param name: 待检查的域名
        :return: 是否为子域名
        """
        if not name:
            return False
        name_lower = name.lower().strip()
        domain_lower = self.domain.lower()
        if name_lower == domain_lower:
            return True
        if name_lower.endswith('.' + domain_lower):
            return True
        # 处理泛域名: *.example.com → example.com
        if name_lower.startswith('*.'):
            clean = name_lower[2:]
            return clean == domain_lower or clean.endswith('.' + domain_lower)
        return False

    def _extract_subdomains(self, records: list) -> Set[str]:
        """
        从 PDNS 记录中提取子域名

        Robtex 记录格式：
        {"rrname":"sub.example.com","rrtype":"A","rrdata":"1.2.3.4",...}

        :param records: PDNS 记录列表
        :return: 子域名集合
        """
        subdomains = set()
        for record in records:
            rrname = record.get('rrname', '')
            if self._is_subdomain(rrname):
                subdomains.add(rrname.lower())
        return subdomains

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        """简单验证 IP 地址格式"""
        if not ip:
            return False
        ipv4 = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
        ipv6 = re.compile(r'^[0-9a-fA-F:]+$')
        return bool(ipv4.match(ip) or ipv6.match(ip))

    def query(self):
        """
        主查询逻辑：

        1. 正向查询域名 → 从 rrname 提取子域名
        2. 收集 A/AAAA 记录的 IP（去重）
        3. 对每个唯一 IP 反向查询 → 从中提取子域名
        """
        self._setup_headers()
        self.proxy = self.get_proxy(self.source)

        # 步骤 1：正向查询，直接从 rrname 提取子域名
        logger.info(f'{self.source} 正向查询: {self.domain}')
        forward_records = self._query_forward()
        if forward_records:
            subs = self._extract_subdomains(forward_records)
            self.subdomains.update(subs)
            logger.info(
                f'{self.source} 正向查询发现 {len(subs)} 个子域名'
            )

        # 步骤 2：收集唯一 IP
        unique_ips: Set[str] = set()
        for record in forward_records:
            if record.get('rrtype') in self.IP_RRTYPES:
                ip = record.get('rrdata', '')
                if self._is_valid_ip(ip):
                    unique_ips.add(ip)

        if not unique_ips:
            logger.info(f'{self.source} 无唯一 IP 可反查')
            return

        logger.info(f'{self.source} 发现 {len(unique_ips)} 个唯一 IP，开始反查')

        # 步骤 3：IP 反向查询
        for ip in unique_ips:
            logger.debug(f'{self.source} 反查 IP: {ip}')
            reverse_records = self._query_reverse(ip)
            if reverse_records:
                subs = self._extract_subdomains(reverse_records)
                self.subdomains.update(subs)

        logger.info(
            f'{self.source} 总计发现 {len(self.subdomains)} 个唯一子域名'
        )

    def run(self) -> Set[str]:
        """
        类统一执行入口

        :return: 子域名集合
        """
        self.begin()
        self.query()
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块统一调用入口

    :param domain: 目标域名
    :param config: 可选配置字典
    :return: 子域名集合
    """
    module = Robtex(domain, config)
    return module.run()
