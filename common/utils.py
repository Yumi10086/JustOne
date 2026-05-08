import os
import re
import sys
import time
import json
import socket
import random
import string
import platform
import subprocess
from urllib.parse import scheme_chars
from ipaddress import IPv4Address, ip_address
from pathlib import Path

import requests
import tenacity
from dns.resolver import Resolver

from common.database import Database
from common.domain import Domain
from common.records import Record, RecordCollection
from config import settings
from config.logging import logger

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

IP_RE = re.compile(r'^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$')
SCHEME_RE = re.compile(r'^([' + scheme_chars + ']+:)?//')


def gen_random_ip():
    """
    Generate random decimal IP string
    """
    while True:
        ip = IPv4Address(random.randint(0, 2 ** 32 - 1))
        if ip.is_global:
            return ip.exploded


def gen_fake_header():
    """
    Generate fake request headers
    """
    headers = default_headers.copy()
    if settings.http_enable_random_ua:
        ua = random.choice(user_agents)
        headers['User-Agent'] = ua
    headers['Accept-Encoding'] = 'gzip, deflate'
    return headers


def get_random_header():
    """
    Get random header
    """
    headers = gen_fake_header()
    if not isinstance(headers, dict):
        headers = None
    return headers


def get_random_proxy():
    """
    Get random proxy
    """
    if not settings.proxy_enable:
        return None
    try:
        return random.choice(settings.proxy_pool)
    except (IndexError, TypeError):
        return None


def get_proxy():
    """
    Get proxy
    """
    if settings.proxy_enable:
        return get_random_proxy()
    return None


def split_list(ls, size):
    """
    Split list

    :param list ls: list
    :param int size: size
    :return list: result
    """
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
            logger.error('Use targets parameter for multiple domain names')
            exit(1)
        domain = match_main_domain(target)
        if not domain:
            return domains
        domains.add(domain)
    return domains


def get_from_targets(targets):
    domains = set()
    if not isinstance(targets, str):
        return domains
    try:
        path = Path(targets)
    except Exception as e:
        logger.error(e)
        return domains
    if path.exists() and path.is_file():
        domains = read_target_file(targets)
        return domains
    return domains


def get_domains(target, targets=None):
    logger.debug(f'Getting domains')
    target_domains = get_from_target(target)
    targets_domains = get_from_targets(targets)
    domains = list(target_domains.union(targets_domains))
    if targets_domains:
        domains = sorted(domains, key=targets_domains.index)
    if not domains:
        logger.error(f'Did not get a valid domain name')
    logger.debug(f'The obtained domains \n{domains}')
    return domains


def check_dir(dir_path):
    if not dir_path.exists():
        logger.info(f'{dir_path} does not exist, directory will be created')
        dir_path.mkdir(parents=True, exist_ok=True)


def check_path(path, name, fmt):
    """
    检查结果输出目录路径

    :param path: 保存路径
    :param name: 导出名字
    :param fmt: 保存格式
    :return: 保存路径
    """
    filename = f'{name}.{fmt}'
    default_path = settings.results_dir / filename
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
        logger.warning(f'{parent_dir} does not exist, directory will be created')
        parent_dir.mkdir(parents=True, exist_ok=True)
    if path.exists():
        logger.warning(f'The {path} exists and will be overwritten')
    return path


def check_format(fmt):
    """
    检查导出格式

    :param fmt: 传入的导出格式
    :return: 导出格式
    """
    formats = ['csv', 'json']
    if fmt in formats:
        return fmt
    else:
        logger.warning(f'Does not support {fmt} format')
        logger.warning('So use csv format by default')
        return 'csv'


def load_json(path):
    with open(path) as fp:
        return json.load(fp)


def save_to_db(name, data, module):
    """
    Save request results to database

    :param str  name: table name
    :param list data: data to be saved
    :param str module: module name
    """
    db = Database()
    db.drop_table(name)
    db.create_table(name)
    db.save_db(name, data, module)
    db.close()


def save_to_file(path, data):
    """
    保存数据到文件

    :param path: 保存路径
    :param data: 待存数据
    :return: 保存成功与否
    """
    try:
        with open(path, 'w', errors='ignore', newline='') as file:
            file.write(data)
            return True
    except TypeError:
        with open(path, 'wb') as file:
            file.write(data)
            return True
    except Exception as e:
        logger.error(e)
        return False


def check_response(method, resp):
    """
    检查响应 输出非正常响应返回json的信息

    :param method: 请求方法
    :param resp: 响应体
    :return: 是否正常响应
    """
    if resp.status_code == 200 and resp.content:
        return True
    logger.warning(f'{method} {resp.url} {resp.status_code} - '
                        f'{resp.reason} {len(resp.content)}')
    content_type = resp.headers.get('Content-Type')
    if content_type and 'json' in content_type and resp.content:
        try:
            msg = resp.json()
        except Exception as e:
            logger.debug(e)
        else:
            logger.warning(msg)
    return False


def mark_subdomain(old_data, now_data):
    """
    标记新增子域并返回新的数据集

    :param list old_data: 之前子域数据
    :param list now_data: 现在子域数据
    :return: 标记后的的子域数据
    :rtype: list
    """
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


def export_all_results(path, name, fmt, datas):
    path = check_path(path, name, fmt)
    logger.warning(f'The subdomain result for all main domains: {path}')
    row_list = list()
    for row in datas:
        if 'header' in row:
            row.pop('header')
        if 'response' in row:
            row.pop('response')
        keys = row.keys()
        values = row.values()
        row_list.append(Record(keys, values))
    rows = RecordCollection(iter(row_list))
    content = rows.export(fmt)
    save_to_file(path, content)


def export_all_subdomains(alive, path, name, datas):
    path = check_path(path, name, 'txt')
    logger.warning(f'The txt subdomain result for all main domains: {path}')
    subdomains = set()
    for row in datas:
        subdomain = row.get('subdomain')
        if alive:
            if not row.get('alive'):
                continue
            subdomains.add(subdomain)
        else:
            subdomains.add(subdomain)
    data = '\n'.join(subdomains)
    save_to_file(path, data)


def export_all(alive, fmt, path, datas):
    """
    将所有结果数据导出

    :param bool alive: 只导出存活子域结果
    :param str fmt: 导出文件格式
    :param str path: 导出文件路径
    :param list datas: 待导出的结果数据
    """
    fmt = check_format(fmt)
    timestamp = get_timestring()
    name = f'all_subdomain_result_{timestamp}'
    export_all_results(path, name, fmt, datas)
    export_all_subdomains(alive, path, name, datas)


def dns_resolver():
    """
    dns解析器
    """
    resolver = Resolver()
    resolver.nameservers = settings.dns_nameservers
    resolver.timeout = settings.dns_timeout
    resolver.lifetime = 10.0
    return resolver


def dns_query(qname, qtype):
    """
    查询域名DNS记录

    :param str qname: 待查域名
    :param str qtype: 查询类型
    :return: 查询结果
    """
    logger.trace(f'Try to query {qtype} record of {qname}')
    resolver = dns_resolver()
    try:
        answer = resolver.query(qname, qtype)
    except Exception as e:
        logger.trace(e)
        logger.trace(f'Query {qtype} record of {qname} failed')
        return None
    else:
        logger.trace(f'Query {qtype} record of {qname} succeeded')
        return answer


def get_timestamp():
    return int(time.time())


def get_timestring():
    return time.strftime('%Y%m%d_%H%M%S', time.localtime(time.time()))


def get_classname(classobj):
    return classobj.__class__.__name__


def python_version():
    return sys.version


def calc_alive(data):
    return len(list(filter(lambda item: item.get('alive') == 1, data)))


def count_alive(name):
    db = Database()
    result = db.count_alive(name)
    count = result.scalar()
    db.close()
    return count


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
        except Exception as e:
            logger.error(e)


@tenacity.retry(stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_fixed(2))
def check_net():
    urls = ['http://ip-api.com/json/']
    url = random.choice(urls)
    header = {'User_Agent': 'curl'}
    timeout = settings.http_timeout
    verify = settings.http_verify_ssl
    logger.debug(f'Trying to access {url}')
    session = requests.Session()
    session.trust_env = False
    try:
        rsp = session.get(url, headers=header, timeout=timeout, verify=verify)
    except Exception as e:
        logger.error(e)
        logger.warning('Unable to access Internet, retrying...')
        raise e
    logger.debug('Access to Internet OK')
    country = rsp.json().get('country').lower()
    if country in ['cn', 'china']:
        logger.debug(f'The computer is located in China')
        return True, True
    else:
        logger.debug(f'The computer is not located in China')
        return True, False


def check_dep():
    logger.info('Checking dependent environment')
    implementation = platform.python_implementation()
    version = platform.python_version()
    if implementation != 'CPython':
        logger.error(f'JustOne only passed the test under CPython')
        exit(1)
    if version < '3.8':
        logger.error('JustOne requires Python 3.8 or higher')
        exit(1)


def get_net_env():
    logger.info('Checking network environment')
    try:
        result = check_net()
    except Exception as e:
        logger.debug(e)
        logger.warning('Please check your network environment.')
        return False, None
    return result


def check_version(local):
    logger.info('Checking for the latest version')
    api = 'https://api.github.com/repos/shmilylty/OneForAll/releases/latest'
    header = get_random_header()
    proxy = get_proxy()
    timeout = settings.http_timeout
    verify = settings.http_verify_ssl
    session = requests.Session()
    session.trust_env = False
    try:
        resp = session.get(url=api, headers=header, proxies=proxy,
                           timeout=timeout, verify=verify)
        resp_json = resp.json()
        latest = resp_json['tag_name']
    except Exception as e:
        logger.warning('An error occurred while checking the latest version')
        logger.debug(e)
        return
    if latest > local:
        change = resp_json.get("body")
        logger.warning(f'The current version is {local} '
                            f'but the latest version is {latest}')
        logger.warning(f'The {latest} version mainly has the following changes')
        logger.warning(change)
    else:
        logger.info(f'The current version {local} is already the latest version')


def get_main_domain(domain):
    if not isinstance(domain, str):
        return None
    return Domain(domain).registered()


def call_massdns(massdns_path, dict_path, ns_path, output_path, log_path,
                 query_type='A', process_num=1, concurrent_num=10000,
                 quiet_mode=False):
    logger.debug('Start running massdns')
    quiet = ''
    if quiet_mode:
        quiet = '--quiet'
    status_format = 'ansi'
    socket_num = 1
    resolve_num = 15
    cmd = f'{massdns_path} {quiet} --status-format {status_format} ' \
          f'--processes {process_num} --socket-count {socket_num} ' \
          f'--hashmap-size {concurrent_num} --resolvers {ns_path} ' \
          f'--resolve-count {resolve_num} --type {query_type} ' \
          f'--flush --output J --outfile {output_path} ' \
          f'--root --error-log {log_path} {dict_path} --filter OK ' \
          f'--sndbuf 0 --rcvbuf 0'
    logger.debug(f'Run command {cmd}')
    subprocess.run(args=cmd, shell=True)
    logger.debug(f'Finished massdns')


def get_massdns_path(massdns_dir):
    path = None
    system = platform.system().lower()
    machine = platform.machine().lower()
    name = f'massdns_{system}_{machine}'
    if system == 'windows':
        name = f'massdns.exe'
        if machine == 'amd64':
            massdns_dir = massdns_dir.joinpath('windows', 'x64')
        else:
            massdns_dir = massdns_dir.joinpath('windows', 'x86')
    path = massdns_dir.joinpath(name)
    if not path.exists():
        logger.error('There is no massdns for this platform or architecture')
        logger.info('Please try to compile massdns yourself '
                            'and specify the path in the configuration')
        exit(0)
    return path


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
    except Exception as e:
        logger.error(e)
        return 0
    return int(ipv4)


def match_subdomains(domain, html, distinct=True, fuzzy=True):
    """
    Use regexp to match subdomains

    :param  str domain: main domain
    :param  str html: response html text
    :param  bool distinct: deduplicate results or not (default True)
    :param  bool fuzzy: fuzzy match subdomain or not (default True)
    :return set/list: result set or list
    """
    logger.trace(f'Use regexp to match subdomains in the response body')
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
        logger.warning(f'The generated dictionary is empty')
        return
    for subdomain in subdomains:
        if subdomain:
            logger.warning(f'Please check whether {subdomain} is correct or not')
            return


def get_url_resp(url):
    logger.info(f'Attempting to request {url}')
    timeout = settings.http_timeout
    verify = settings.http_verify_ssl
    session = requests.Session()
    session.trust_env = False
    try:
        resp = session.get(url, params=None, timeout=timeout, verify=verify)
    except Exception as e:
        logger.warning(f'Error request {url}')
        logger.debug(e)
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
    """Does the given str look like an IP address?"""
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


def deal_data(domain):
    db = Database()
    db.remove_invalid(domain)
    db.deduplicate_subdomain(domain)
    db.close()


def get_data(domain):
    db = Database()
    data = db.get_data(domain).as_dict()
    db.close()
    return data


def clear_data(domain):
    db = Database()
    db.drop_table(domain)
    db.close()


def get_ns_path(in_china=None, enable_wildcard=None, ns_ip_list=None):
    data_dir = settings.data_dir
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


def init_table(domain):
    db = Database()
    db.drop_table(domain)
    db.create_table(domain)
    db.close()