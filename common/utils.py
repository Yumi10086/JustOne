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
    http_config['timeout'] = timeout
    http_config['verify_ssl'] = verify_ssl
    http_config['enable_random_ua'] = enable_random_ua
    http_config['proxy_enable'] = proxy_enable
    http_config['proxy_pool'] = proxy_pool or []
    http_config['dns_nameservers'] = dns_nameservers or ['223.5.5.5', '119.29.29.29']
    http_config['dns_timeout'] = dns_timeout


def gen_random_ip():
    while True:
        ip = IPv4Address(random.randint(0, 2 ** 32 - 1))
        if ip.is_global:
            return ip.exploded


def gen_fake_header(enable_random_ua: bool = None):
    headers = default_headers.copy()
    if enable_random_ua or (enable_random_ua is None and http_config['enable_random_ua']):
        headers['User-Agent'] = random.choice(user_agents)
    headers['Accept-Encoding'] = 'gzip, deflate'
    return headers


def get_random_header():
    headers = gen_fake_header()
    if not isinstance(headers, dict):
        headers = None
    return headers


def get_random_proxy():
    if not http_config['proxy_enable']:
        return None
    try:
        return random.choice(http_config['proxy_pool'])
    except (IndexError, TypeError):
        return None


def get_proxy():
    if http_config['proxy_enable']:
        return get_random_proxy()
    return None


def split_list(ls, size):
    if size == 0:
        return ls
    return [ls[i:i + size] for i in range(0, len(ls), size)]


def match_main_domain(domain):
    if not isinstance(domain, str):
        return None
    item = domain.lower().strip()
    return Domain(item).match()


def read_target_file(target):
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
    domains = set()
    if isinstance(target, str):
        if target.endswith('.txt'):
            raise ValueError('Use targets parameter for multiple domain names')
        domain = match_main_domain(target)
        if not domain:
            return domains
        domains.add(domain)
    return domains


def get_from_targets(targets):
    domains = set()
    if not isinstance(targets, str):
        return domains
    path = Path(targets)
    if path.exists() and path.is_file():
        domains = read_target_file(targets)
        return domains
    return domains


def get_domains(target, targets=None):
    target_domains = get_from_target(target)
    targets_domains = get_from_targets(targets)
    domains = list(target_domains.union(targets_domains))
    if targets_domains:
        domains = sorted(domains, key=targets_domains.index)
    if not domains:
        raise ValueError('Did not get a valid domain name')
    return domains


def check_dir(dir_path):
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
    return asyncio.run(check_net_async(timeout, verify))


def get_net_env():
    return check_net()


def get_main_domain(domain):
    if not isinstance(domain, str):
        return None
    return Domain(domain).registered()


def is_subname(name):
    chars = string.ascii_lowercase + string.digits + '.-'
    for char in name:
        if char not in chars:
            return False
    return True


def ip_to_int(ip):
    if isinstance(ip, int):
        return ip
    try:
        ipv4 = IPv4Address(ip)
    except Exception:
        return 0
    return int(ipv4)


def match_subdomains(domain, html, distinct=True, fuzzy=True):
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