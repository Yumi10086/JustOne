"""
子域名信息丰富模块
从 SQLite 数据库读取已有子域名，通过 DNS 解析、HTTP 探测、CDN 识别、IP 地理/ASN 查询等方式丰富信息并更新数据库。
"""

import asyncio
import concurrent.futures
import ipaddress
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

import aiohttp

from common.database import Database
from common import resolve as dns_resolve
from common import utils
from common.ipasn import IPAsnInfo
from config.logging import logger


TITLE_RE = re.compile(rb'<title[^>]*>([^<]+)</title>', re.IGNORECASE)

ALIVE_CODES = {
    200, 201, 202, 203, 204, 205, 206, 207, 208, 226,
    301, 302, 303, 307, 308,
    400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410,
    411, 412, 413, 414, 415, 416, 417, 418, 421, 422, 423,
    424, 426, 428, 429, 431, 451,
    500, 501, 502, 503, 504, 505, 506, 507, 508, 510, 511,
}


class Enrich:
    """
    子域名信息丰富器

    三阶段管道:
    1. DNS 解析（并行线程池）—— 补充 IP、CNAME
    2. HTTP 探测（异步并发）—— 补充状态码、页面标题、响应头、Banner
    3. IP 定位 + CDN 识别（无网络，纯本地）—— 补充 CIDR、ASN、ORG、CDN 标记
    """

    def __init__(self, db_path: str, concurrent: int = 200, timeout: int = 10):
        """
        :param str db_path: SQLite 数据库文件路径
        :param int concurrent: DNS 线程数 / HTTP 并发数
        :param int timeout: HTTP 请求超时（秒）
        """
        self.db_path = Path(db_path)
        self.concurrent = concurrent
        self.timeout = timeout
        self._db: Optional[Database] = None
        self.table_name: Optional[str] = None
        self.domain: Optional[str] = None
        self.records: List[Dict[str, Any]] = []
        self.cdn_ip_ranges: List[ipaddress.IPv4Network] = []
        self._load_cdn_ranges()

    def _load_cdn_ranges(self):
        """加载 CDN IP CIDR 特征（用于本地 IP 匹配，避免 DNS 查询）"""
        cidr_file = Path(__file__).parent.parent / 'data' / 'cdn_ip_cidr.json'
        if cidr_file.exists():
            with open(cidr_file, 'r', encoding='utf-8') as f:
                cidrs = json.load(f)
            for cidr in cidrs:
                try:
                    self.cdn_ip_ranges.append(ipaddress.ip_network(cidr))
                except ValueError:
                    continue
            logger.debug(f'加载 {len(self.cdn_ip_ranges)} 条 CDN IP CIDR 特征')

    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = Database(str(self.db_path))
        return self._db

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def _detect_table(self) -> Optional[str]:
        result = self.db.query(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "ORDER BY rowid DESC LIMIT 1"
        )
        if result.success and result.data:
            return result.data[0][0]
        return None

    def load(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """从数据库加载子域名记录"""
        if not table_name:
            table_name = self._detect_table()
        if not table_name:
            logger.error('数据库中无可用表')
            return []

        self.table_name = table_name
        self.domain = table_name.replace('_', '.')
        logger.info(f'从表 [{table_name}] 加载数据（域名: {self.domain}）')

        result = self.db.get_data(table_name)
        if not result.success or not result.data:
            logger.warning(f'表 {table_name} 中无数据')
            return []

        self.records = [dict(row) for row in result.data]
        logger.info(f'加载了 {len(self.records)} 条记录')
        return self.records

    def _update_record(self, row_id: int, data: Dict[str, Any]) -> bool:
        """更新单条数据库记录"""
        if not data or not self.table_name:
            return False
        safe_table = self.table_name.replace('"', '')
        set_parts = [f'"{k}" = ?' for k in data]
        set_str = ', '.join(set_parts)
        sql = f'UPDATE "{safe_table}" SET {set_str} WHERE id = ?'
        params = tuple(data.values()) + (row_id,)
        return self.db.query(sql, params).success

    def _is_cdn_ip(self, ip: str) -> bool:
        """通过 IP CIDR 判断是否 CDN（本地查询，无网络）"""
        try:
            addr = ipaddress.ip_address(ip.strip())
            for network in self.cdn_ip_ranges:
                if addr in network:
                    return True
        except ValueError:
            pass
        return False

    @staticmethod
    async def _http_probe(subdomain: str, session: aiohttp.ClientSession,
                          timeout: int, ip: str = '') -> Dict[str, Any]:
        """
        HTTP 探测：通过 IP 直连获取状态码、页面标题、响应头

        使用已知 IP + Host header 绕过 aiohttp 的系统 DNS 解析，
        避免 socket.gaierror。
        """
        result: Dict[str, Any] = {'status': None, 'alive': 0, 'title': '', 'header': '', 'banner': ''}

        first_ip = ip.split(',')[0].strip() if ip else ''
        if not first_ip:
            return result

        for scheme in ('http://', 'https://'):
            url = scheme + first_ip
            try:
                async with session.get(
                    url,
                    headers={'Host': subdomain},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    allow_redirects=False,
                    ssl=False,
                ) as resp:
                    if resp.status not in ALIVE_CODES:
                        continue

                    result['status'] = resp.status
                    result['alive'] = 1

                    raw_headers = dict(resp.headers)
                    header_str = json.dumps(raw_headers, ensure_ascii=False)
                    result['header'] = header_str[:2000]
                    result['banner'] = utils.get_sample_banner(raw_headers)[:500]

                    try:
                        body = await resp.read()
                        m = TITLE_RE.search(body)
                        if m:
                            result['title'] = m.group(1).decode('utf-8', errors='replace').strip()[:500]
                    except Exception:
                        pass
                    break
            except (OSError, asyncio.TimeoutError, aiohttp.ClientError):
                continue

        return result

    async def enrich(self, show_progress: bool = True) -> int:
        """
        执行信息丰富流程（三阶段并行管道）

        :param show_progress: 是否打印进度日志
        :return: 更新成功的记录数
        """
        if not self.records:
            logger.warning('无数据需要丰富')
            return 0

        total = len(self.records)
        total_updated = 0

        # ============ Phase 1: DNS 解析（线程池并行）============
        need_dns = [(r['id'], r['subdomain']) for r in self.records
                    if r.get('subdomain') and not r.get('ip')]
        if need_dns:
            logger.info(f'[1/3] DNS 解析: {len(need_dns)} 个子域名（并发 {min(50, self.concurrent)}）')
            dns_updated = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(50, self.concurrent)) as pool:
                loop = asyncio.get_running_loop()
                tasks = [
                    (rid, loop.run_in_executor(pool, dns_resolve.resolve_domain, sub))
                    for rid, sub in need_dns
                ]
                for idx, (rid, task) in enumerate(tasks):
                    info = await task
                    if info and info.get('resolve'):
                        data = {
                            'resolve': info.get('resolve', 0),
                            'alive': info.get('alive', 0),
                            'ip': info.get('ip', ''),
                            'cname': info.get('cname', ''),
                            'reason': info.get('reason', ''),
                        }
                        if self._update_record(rid, data):
                            # 同步更新内存记录
                            for r in self.records:
                                if r['id'] == rid:
                                    r.update(data)
                                    break
                            dns_updated += 1

                    if show_progress and (idx + 1) % 500 == 0:
                        logger.info(f'  DNS 进度: {idx + 1}/{len(need_dns)}，已解析 {dns_updated}')
            logger.info(f'  DNS 完成: 解析成功 {dns_updated}/{len(need_dns)}')
            total_updated += dns_updated
        else:
            logger.info('[1/3] DNS 解析: 无需执行（所有记录已有 IP）')

        # ============ Phase 2: HTTP 探测（aiohttp 并发）============
        need_http = [(r['id'], r['subdomain'], r.get('ip', '')) for r in self.records
                     if r.get('subdomain') and not r.get('status') and r.get('ip')]
        if need_http:
            logger.info(f'[2/3] HTTP 探测: {len(need_http)} 个子域名（并发 {self.concurrent}）')
            http_updated = 0
            semaphore = asyncio.Semaphore(self.concurrent)
            connector = aiohttp.TCPConnector(limit=self.concurrent, limit_per_host=self.concurrent)

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=connector,
            ) as session:
                async def probe_one(rid: int, sub: str, ip: str):
                    nonlocal http_updated
                    async with semaphore:
                        info = await self._http_probe(sub, session, self.timeout, ip=ip)
                        if info.get('status'):
                            data = {
                                'status': info['status'],
                                'alive': 1,
                                'title': info.get('title', ''),
                                'header': info.get('header', ''),
                                'banner': info.get('banner', ''),
                            }
                            if self._update_record(rid, data):
                                for r in self.records:
                                    if r['id'] == rid:
                                        r.update(data)
                                        break
                                http_updated += 1

                # 分批提交，避免一次 gather 海量协程
                chunk_size = self.concurrent * 2
                for start in range(0, len(need_http), chunk_size):
                    chunk = need_http[start:start + chunk_size]
                    await asyncio.gather(*[probe_one(rid, sub, ip) for rid, sub, ip in chunk])
                    if show_progress:
                        done = min(start + chunk_size, len(need_http))
                        logger.info(f'  HTTP 进度: {done}/{len(need_http)}，存活 {http_updated}')

            logger.info(f'  HTTP 完成: 存活 {http_updated}/{len(need_http)}')
            total_updated += http_updated
        else:
            logger.info('[2/3] HTTP 探测: 无需执行')

        # ============ Phase 3: IP 定位 + CDN 识别（纯本地，无网络）============
        logger.info('[3/3] IP 丰富: CDN 识别 + ASN/ORG 查询')
        ip_updated = 0
        ip_asn = IPAsnInfo()
        for idx, record in enumerate(self.records):
            ip = record.get('ip', '')
            if not ip:
                continue

            enrich_data: Dict[str, Any] = {}
            first_ip = ip.split(',')[0].strip()
            if not first_ip:
                continue

            # CDN 识别（IP CIDR 匹配，无 DNS 查询）
            if not record.get('cdn'):
                if self._is_cdn_ip(first_ip):
                    enrich_data['cdn'] = 1

            # IP ASN / ORG 查询
            if not record.get('asn'):
                asn_info = ip_asn.find(first_ip)
                if asn_info:
                    if asn_info.get('cidr'):
                        enrich_data['cidr'] = asn_info['cidr']
                    if asn_info.get('asn'):
                        enrich_data['asn'] = asn_info['asn']
                    if asn_info.get('org'):
                        enrich_data['org'] = asn_info['org']

            if enrich_data:
                if self._update_record(record['id'], enrich_data):
                    record.update(enrich_data)
                    ip_updated += 1

            if show_progress and (idx + 1) % 1000 == 0:
                logger.info(f'  IP 丰富进度: {idx + 1}/{total}，已更新 {ip_updated}')

        logger.info(f'  IP 丰富完成: 更新 {ip_updated}/{total}')
        total_updated += ip_updated

        logger.info(f'信息丰富全部完成，共更新 {total_updated} 条记录')
        return total_updated

    def run(self, table_name: Optional[str] = None) -> int:
        """同步入口"""
        try:
            self.load(table_name)
            if not self.records:
                return 0
            return asyncio.run(self.enrich())
        finally:
            self.close()


def run(db_path: str, table_name: Optional[str] = None, concurrent: int = 200) -> int:
    """模块执行入口"""
    enricher = Enrich(db_path, concurrent=concurrent)
    return enricher.run(table_name)
