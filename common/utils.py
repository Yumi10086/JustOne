"""
工具函数模块
"""

import os
import re
import time
import json
import socket
import random
import string
import asyncio
from urllib.parse import scheme_chars
from ipaddress import IPv4Address, ip_address
from pathlib import Path

import requests
from dns.resolver import Resolver

from common.domain import Domain

IP_RE = re.compile(r'^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$')
SCHEME_RE = re.compile(r'^([' + scheme_chars + ']+:)?//')

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/68.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:61.0) '
    'Gecko/20100101 Firefox/68.0',
    'Mozilla/5.0 (X11; Linux i586; rv:31.0) Gecko/20100101 Firefox/68.0']

default_headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    'Cache-Control': 'max-age=0',
    'DNT': '1',
    'Referer': 'https://www.google.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
    'Upgrade-Insecure-Requests': '1',
    'X-Forwarded-For': '127.0.0.1'
}


http_config = {
    'timeout': 27,
    'verify_ssl': False,
    'enable_random_ua': True,
    'proxy_enable': False,
    'proxy_pool': [],
    'dns_nameservers': ['223.5.5.5', '119.29.29.29'],
    'dns_timeout': 5,
}


def set_http_config(
    timeout: int = 27,
    verify_ssl: bool = False,
    enable_random_ua: bool = True,
    proxy_enable: bool = False,
    proxy_pool: list = None,
    dns_nameservers: list = None,
    dns_timeout: int = 5,
):
    """
    设置全局 HTTP 配置

    :param int timeout: 超时时间（秒）
    :param bool verify_ssl: 是否验证 SSL 证书
    :param bool enable_random_ua: 是否启用随机 User-Agent
    :param bool proxy_enable: 是否启用代理
    :param list proxy_pool: 代理池列表
    :param list dns_nameservers: DNS 服务器列表
    :param int dns_timeout: DNS 超时时间（秒）
    """
    http_config['timeout'] = timeout
    http_config['verify_ssl'] = verify_ssl
    http_config['enable_random_ua'] = enable_random_ua
    http_config['proxy_enable'] = proxy_enable
    http_config['proxy_pool'] = proxy_pool or []
    http_config['dns_nameservers'] = dns_nameservers or ['223.5.5.5', '119.29.29.29']
    http_config['dns_timeout'] = dns_timeout


def gen_random_ip():
    """
    生成随机公网 IP 地址

    :return: 随机公网 IP 字符串
    """
    while True:
        ip = IPv4Address(random.randint(0, 2 ** 32 - 1))
        if ip.is_global:
            return ip.exploded


def gen_fake_header(enable_random_ua: bool = None):
    """
    生成伪造的 HTTP 请求头

    :param bool enable_random_ua: 是否使用随机 User-Agent
    :return: 请求头字典
    """
    headers = default_headers.copy()
    if enable_random_ua or (enable_random_ua is None and http_config['enable_random_ua']):
        headers['User-Agent'] = random.choice(user_agents)
    headers['Accept-Encoding'] = 'gzip, deflate'
    return headers


def get_random_header():
    """
    获取随机请求头

    :return: 请求头字典
    """
    headers = gen_fake_header()
    if not isinstance(headers, dict):
        headers = None
    return headers


def get_random_proxy():
    """
    获取随机代理

    :return: 代理字典，未启用返回 None
    """
    if not http_config['proxy_enable']:
        return None
    try:
        return random.choice(http_config['proxy_pool'])
    except (IndexError, TypeError):
        return None


def get_proxy():
    """
    获取代理（根据配置）

    :return: 代理字典，未启用返回 None
    """
    if http_config['proxy_enable']:
        return get_random_proxy()
    return None


def split_list(ls, size):
    """
    将列表分割为指定大小的子列表

    :param list ls: 要分割的列表
    :param int size: 每个子列表的大小
    :return: 子列表的列表
    """
    if size == 0:
        return ls
    return [ls[i:i + size] for i in range(0, len(ls), size)]


def match_main_domain(domain):
    """
    匹配主域名

    :param domain: 域名或 URL 字符串
    :return: 匹配的主域名，未匹配返回 None
    """
    if not isinstance(domain, str):
        return None
    item = domain.lower().strip()
    return Domain(item).match()


def read_target_file(target):
    """
    从目标文件读取域名列表

    :param target: 文件路径
    :return: 域名列表
    """
    domains = list()
    with open(target, encoding='utf-8', errors='ignore') as file:
        for line in file:
            domain = match_main_domain(line)
            if not domain:
                continue
            domains.append(domain)
    sorted_domains = sorted(set(domains), key=domains.index)
    return sorted_domains


def get_from_target(target):
    """
    从单个目标获取域名

    :param target: 目标字符串（域名或 URL）
    :return: 域名集合
    """
    domains = set()
    if isinstance(target, str):
        if target.endswith('.txt'):
            raise ValueError('使用 targets 参数处理多个域名')
        domain = match_main_domain(target)
        if not domain:
            return domains
        domains.add(domain)
    return domains


def get_from_targets(targets):
    """
    从目标文件获取域名列表

    :param targets: 目标文件路径
    :return: 域名集合
    """
    domains = set()
    if not isinstance(targets, str):
        return domains
    path = Path(targets)
    if path.exists() and path.is_file():
        domains = read_target_file(targets)
        return domains
    return domains


def get_domains(target, targets=None):
    """
    获取域名列表

    :param target: 目标域名或文件
    :param targets: 目标文件路径
    :return: 域名列表
    """
    target_domains = get_from_target(target)
    targets_domains = get_from_targets(targets)
    domains = list(target_domains.union(targets_domains))
    if targets_domains:
        domains = sorted(domains, key=targets_domains.index)
    if not domains:
        raise ValueError('未获取到有效的域名')
    return domains


def check_dir(dir_path):
    """
    检查并创建目录

    :param dir_path: 目录路径
    """
    if not dir_path.exists():
        dir_path.mkdir(parents=True, exist_ok=True)


def check_path(path, name, fmt, results_dir=None):
    filename = f'{name}.{fmt}'
    default_path = (results_dir or Path('results')) / filename
    if isinstance(path, str):
        path = repr(path).replace('\\', '/')
        path = path.replace('\'', '')
    else:
        path = default_path
    path = Path(path)
    if path.is_dir():
        path = path.joinpath(filename)
    parent_dir = path.parent
    if not parent_dir.exists():
        parent_dir.mkdir(parents=True, exist_ok=True)
    return path


def check_format(fmt):
    formats = ['csv', 'json']
    if fmt in formats:
        return fmt
    return 'csv'


def load_json(path):
    with open(path) as fp:
        return json.load(fp)


def save_to_file(path, data):
    try:
        with open(path, 'w', errors='ignore', newline='') as file:
            file.write(data)
            return True
    except TypeError:
        with open(path, 'wb') as file:
            file.write(data)
            return True
    except Exception:
        return False


def check_response(method, resp):
    if resp.status_code == 200 and resp.content:
        return True
    return False


def mark_subdomain(old_data, now_data):
    mark_data = now_data.copy()
    if not old_data:
        for index, item in enumerate(mark_data):
            item['new'] = 1
            mark_data[index] = item
        return mark_data
    old_subdomains = {item.get('subdomain') for item in old_data}
    for index, item in enumerate(mark_data):
        subdomain = item.get('subdomain')
        if subdomain in old_subdomains:
            item['new'] = 0
        else:
            item['new'] = 1
        mark_data[index] = item
    return mark_data


def remove_invalid_string(string):
    return re.sub(r'[\000-\010]|[\013-\014]|[\016-\037]', r'', string)


def get_timestamp():
    return int(time.time())


def get_timestring():
    return time.strftime('%Y%m%d_%H%M%S', time.localtime(time.time()))


def get_classname(classobj):
    return classobj.__class__.__name__


def calc_alive(data):
    return len(list(filter(lambda item: item.get('alive') == 1, data)))


def get_subdomains(data):
    return set(map(lambda item: item.get('subdomain'), data))


def set_id_none(data):
    new_data = []
    for item in data:
        item['id'] = None
        new_data.append(item)
    return new_data


def get_filtered_data(data):
    filtered_data = []
    for item in data:
        resolve = item.get('resolve')
        if resolve != 1:
            filtered_data.append(item)
    return filtered_data


def get_sample_banner(headers):
    temp_list = []
    server = headers.get('Server')
    if server:
        temp_list.append(server)
    via = headers.get('Via')
    if via:
        temp_list.append(via)
    power = headers.get('X-Powered-By')
    if power:
        temp_list.append(power)
    banner = ','.join(temp_list)
    return banner


def check_ip_public(ip_list):
    for ip_str in ip_list:
        ip = ip_address(ip_str)
        if not ip.is_global:
            return 0
    return 1


def ip_is_public(ip_str):
    ip = ip_address(ip_str)
    if not ip.is_global:
        return 0
    return 1


def get_request_count():
    return os.cpu_count() * 16


def uniq_dict_list(dict_list):
    return list(filter(lambda name: dict_list.count(name) == 1, dict_list))


def delete_file(*paths):
    for path in paths:
        try:
            path.unlink()
        except Exception:
            pass


async def check_net_async(timeout: int = None, verify: bool = None):
    urls = ['http://ip-api.com/json/']
    url = random.choice(urls)
    header = {'User_Agent': 'curl'}
    timeout = timeout or http_config['timeout']
    verify = verify if verify is not None else http_config['verify_ssl']

    for attempt in range(3):
        try:
            async with asyncio.timeout(timeout):
                rsp = requests.get(url, headers=header, timeout=timeout, verify=verify)
                break
        except Exception:
            await asyncio.sleep(2)
            continue
    else:
        return False, None

    country = rsp.json().get('country').lower()
    in_china = country in ['cn', 'china']
    return True, in_china


def check_net(timeout: int = None, verify: bool = None):
    """
    检查网络连接（同步版本）

    :param int timeout: 超时时间
    :param bool verify: 是否验证 SSL
    :return: (是否联网, 是否在中国)
    """
    return asyncio.run(check_net_async(timeout, verify))


def get_net_env():
    """
    获取网络环境信息

    :return: (是否联网, 是否在中国)
    """
    return check_net()


def get_main_domain(domain):
    """
    获取主域名

    :param domain: 域名字符串
    :return: 注册域名
    """
    if not isinstance(domain, str):
        return None
    return Domain(domain).registered()


def is_subname(name):
    """
    判断是否为有效的子域名格式

    :param name: 域名或子域名
    :return: 是否有效
    """
    chars = string.ascii_lowercase + string.digits + '.-'
    for char in name:
        if char not in chars:
            return False
    return True


def ip_to_int(ip):
    """
    将 IP 地址转换为整数

    :param ip: IP 地址字符串或整数
    :return: 整数形式的 IP
    """
    if isinstance(ip, int):
        return ip
    try:
        ipv4 = IPv4Address(ip)
    except Exception:
        return 0
    return int(ipv4)


def match_subdomains(domain, html, distinct=True, fuzzy=True):
    """
    从 HTML 响应中匹配子域名

    :param domain: 主域名
    :param html: HTML 响应文本
    :param bool distinct: 是否去重
    :param bool fuzzy: 是否模糊匹配
    :return: 子域名集合或列表
    """
    if fuzzy:
        regexp = r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.){0,}' \
                 + domain.replace('.', r'\.')
        result = re.findall(regexp, html, re.I)
        if not result:
            return set()
        deal = map(lambda s: s.lower(), result)
        if distinct:
            return set(deal)
        else:
            return list(deal)
    else:
        regexp = r'(?:\>|\"|\'|\=|\,)(?:http\:\/\/|https\:\/\/)?' \
                 r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.){0,}' \
                 + domain.replace('.', r'\.')
        result = re.findall(regexp, html, re.I)
    if not result:
        return set()
    regexp = r'(?:http://|https://)'
    deal = map(lambda s: re.sub(regexp, '', s[1:].lower()), result)
    if distinct:
        return set(deal)
    else:
        return list(deal)


def check_random_subdomain(subdomains):
    if not subdomains:
        return
    for subdomain in subdomains:
        if subdomain:
            return


def get_url_resp(url, timeout: int = None, verify: bool = None):
    timeout = timeout or http_config['timeout']
    verify = verify if verify is not None else http_config['verify_ssl']
    session = requests.Session()
    session.trust_env = False
    try:
        resp = session.get(url, params=None, timeout=timeout, verify=verify)
    except Exception:
        return None
    return resp


def decode_resp_text(resp):
    content = resp.content
    if not content:
        return str('')
    try:
        content = str(content, encoding='utf-8', errors='strict')
    except (LookupError, TypeError, UnicodeError):
        try:
            content = str(content, encoding='gb18030', errors='strict')
        except (LookupError, TypeError, UnicodeError):
            content = str(content, errors='replace')
    return content


def sort_by_subdomain(data):
    return sorted(data, key=lambda item: item.get('subdomain'))


def looks_like_ip(maybe_ip):
    if not maybe_ip[0].isdigit():
        return False
    try:
        socket.inet_aton(maybe_ip)
        return True
    except (AttributeError, UnicodeError):
        if IP_RE.match(maybe_ip):
            return True
    except socket.error:
        return False


def dns_resolver(nameservers: list = None, timeout: int = None):
    resolver = Resolver()
    resolver.nameservers = nameservers or http_config['dns_nameservers']
    resolver.timeout = timeout or http_config['dns_timeout']
    resolver.lifetime = 10.0
    return resolver


def dns_query(qname, qtype, nameservers: list = None, timeout: int = None):
    resolver = dns_resolver(nameservers, timeout)
    try:
        answer = resolver.query(qname, qtype)
    except Exception:
        return None
    return answer


def get_logger():
    """获取日志记录器"""
    from config.logging import logger
    return logger


def get_ns_path(data_dir, in_china=None, enable_wildcard=None, ns_ip_list=None):
    path = data_dir / 'nameservers.txt'
    if in_china:
        path = data_dir / 'nameservers_cn.txt'
    if not enable_wildcard:
        return path
    if not ns_ip_list:
        return path
    path = data_dir / 'authoritative_dns.txt'
    ns_data = '\n'.join(ns_ip_list)
    save_to_file(path, ns_data)
    return path