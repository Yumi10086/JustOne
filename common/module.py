"""
模块基类
"""

import json
import time
from pathlib import Path

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config.logging import logger
from common import utils
from common.database import Database

http_config = {
    'timeout': 5,
    'verify_ssl': False,
    'proxy_enable': False,
    'dns_nameservers': [],
}


def set_http_config(config: dict):
    """设置模块全局 HTTP 配置"""
    http_config.update(config)


class Module(object):
    """收集模块基类"""

    def __init__(self, domain: str = '', config: dict = None):
        """
        初始化模块

        :param str domain: 目标域名
        :param dict config: 配置字典
        """
        self.module = 'Module'
        self.source = 'BaseModule'
        self.domain = domain
        self.config = config or {}

        self.cookie = None
        self.header = dict()
        self.proxy = None
        self.delay = 1
        self.timeout = self.config.get('timeout', http_config.get('timeout', 27))
        self.verify = self.config.get('verify_ssl', http_config.get('verify_ssl', False))
        self.proxy_enable = self.config.get('proxy_enable', http_config.get('proxy_enable', False))
        self.results_dir = self.config.get('results_dir', Path.cwd() / 'results')
        self.save_module_result = self.config.get('save_module_result', False)

        self.subdomains = set()
        self.infos = dict()
        self.results = list()
        self.start = time.time()
        self.end = None
        self.elapse = None

    def have_api(self, *apis):
        """
        检查 API 信息是否配置完整

        :param apis: API 配置项集合
        :return bool: 检查结果
        """
        if not all(apis):
            logger.debug(f'{self.source} 模块未配置')
            return False
        return True

    def begin(self):
        """记录模块开始的日志"""
        logger.debug(f'开始 {self.source} 模块收集 {self.domain} 的子域名')

    def finish(self):
        """记录模块结束的日志"""
        self.end = time.time()
        self.elapse = round(self.end - self.start, 1)
        logger.debug(f'{self.source} 模块执行结束')
        logger.info(f'{self.source} 模块耗时 {self.elapse} 秒，发现 {len(self.subdomains)} 个子域名')
        logger.debug(f'{self.source} 模块发现的子域名: {self.subdomains}')

    def head(self, url, params=None, check=True, ignore=False, **kwargs):
        """
        发送 HEAD 请求

        :param str url: 请求 URL
        :param dict params: 请求参数
        :param bool check: 是否检查响应
        :param bool ignore: 是否忽略错误（降低日志级别）
        :param kwargs: 其他参数
        :return: 响应对象
        """
        session = requests.Session()
        session.trust_env = False
        level = 'ERROR'
        if ignore:
            level = 'DEBUG'
        try:
            resp = session.head(url,
                                params=params,
                                cookies=self.cookie,
                                headers=self.header,
                                proxies=self.proxy,
                                timeout=self.timeout,
                                verify=self.verify,
                                **kwargs)
        except Exception as e:
            logger.log(level, e.args[0])
            return None
        if not check:
            return resp
        if utils.check_response('HEAD', resp):
            return resp
        return None

    def get(self, url, params=None, check=True, ignore=False, raise_error=False, **kwargs):
        """
        发送 GET 请求

        :param str url: 请求 URL
        :param dict params: 请求参数
        :param bool check: 是否检查响应
        :param bool ignore: 是否忽略错误
        :param bool raise_error: 是否抛出错误
        :param kwargs: 其他参数
        :return: 响应对象
        """
        session = requests.Session()
        session.trust_env = False
        level = 'ERROR'
        if ignore:
            level = 'DEBUG'
        try:
            resp = session.get(url,
                               params=params,
                               cookies=self.cookie,
                               headers=self.header,
                               proxies=self.proxy,
                               timeout=self.timeout,
                               verify=self.verify,
                               **kwargs)
        except Exception as e:
            if raise_error:
                if isinstance(e, requests.exceptions.ConnectTimeout):
                    logger.log(level, e.args[0])
                    raise e
            logger.log(level, e.args[0])
            return None
        if not check:
            return resp
        if utils.check_response('GET', resp):
            return resp
        return None

    def post(self, url, data=None, check=True, **kwargs):
        """
        发送 POST 请求

        :param str url: 请求 URL
        :param dict data: 请求数据
        :param bool check: 是否检查响应
        :param kwargs: 其他参数
        :return: 响应对象
        """
        session = requests.Session()
        session.trust_env = False
        try:
            resp = session.post(url,
                                data=data,
                                cookies=self.cookie,
                                headers=self.header,
                                proxies=self.proxy,
                                timeout=self.timeout,
                                verify=self.verify,
                                **kwargs)
        except Exception as e:
            logger.error(e.args[0])
            return None
        if not check:
            return resp
        if utils.check_response('POST', resp):
            return resp
        return None

    def delete(self, url, check=True, **kwargs):
        """
        发送 DELETE 请求

        :param str url: 请求 URL
        :param bool check: 是否检查响应
        :param kwargs: 其他参数
        :return: 响应对象
        """
        session = requests.Session()
        session.trust_env = False
        try:
            resp = session.delete(url,
                                   cookies=self.cookie,
                                   headers=self.header,
                                   proxies=self.proxy,
                                   timeout=self.timeout,
                                   verify=self.verify,
                                   **kwargs)
        except Exception as e:
            logger.error(e.args[0])
            return None
        if not check:
            return resp
        if utils.check_response('DELETE', resp):
            return resp
        return None

    def get_header(self):
        """
        获取请求头

        :return: 请求头字典
        """
        headers = utils.gen_fake_header()
        if isinstance(headers, dict):
            self.header = headers
            return headers
        return self.header

    def get_proxy(self, module):
        """
        获取代理

        :param str module: 模块名称
        :return: 代理配置
        """
        if not self.proxy_enable:
            logger.debug('所有模块不使用代理')
            return self.proxy
        logger.debug(f'{module} 模块使用代理')
        return utils.get_random_proxy()

    def match_subdomains(self, resp, distinct=True, fuzzy=True):
        """
        从响应中匹配子域名

        :param resp: 响应对象或字符串
        :param bool distinct: 是否去重
        :param bool fuzzy: 是否模糊匹配
        :return: 子域名集合
        """
        if not resp:
            return set()
        elif isinstance(resp, str):
            return utils.match_subdomains(self.domain, resp, distinct, fuzzy)
        elif hasattr(resp, 'text'):
            return utils.match_subdomains(self.domain, resp.text, distinct, fuzzy)
        else:
            return set()

    def collect_subdomains(self, resp):
        """
        收集子域名

        :param resp: 响应对象或字符串
        :return: 子域名集合
        """
        subdomains = self.match_subdomains(resp)
        self.subdomains.update(subdomains)
        return self.subdomains

    def save_json(self):
        """
        将模块结果保存为 JSON 文件

        :return bool: 是否保存成功
        """
        if not self.save_module_result:
            return False
        logger.debug(f'保存 {self.source} 模块发现的子域名结果为 JSON 文件')
        path = self.results_dir / self.domain / self.module
        path.mkdir(parents=True, exist_ok=True)
        name = self.source + '.json'
        path = path.joinpath(name)
        with open(path, mode='w', errors='ignore') as file:
            result = {'domain': self.domain,
                      'name': self.module,
                      'source': self.source,
                      'elapse': self.elapse,
                      'find': len(self.subdomains),
                      'subdomains': list(self.subdomains),
                      'infos': self.infos}
            json.dump(result, file, ensure_ascii=False, indent=4)
        return True

    def gen_result(self):
        """生成结果列表"""
        logger.debug('正在生成最终结果')
        if not len(self.subdomains):
            logger.debug(f'{self.source} 模块结果为空')
            result = {'id': None,
                      'alive': None,
                      'request': None,
                      'resolve': None,
                      'url': None,
                      'subdomain': None,
                      'port': None,
                      'level': None,
                      'cname': None,
                      'ip': None,
                      'public': None,
                      'cdn': None,
                      'status': None,
                      'reason': None,
                      'title': None,
                      'banner': None,
                      'header': None,
                      'history': None,
                      'response': None,
                      'ip_times': None,
                      'cname_times': None,
                      'ttl': None,
                      'cidr': None,
                      'asn': None,
                      'org': None,
                      'addr': None,
                      'isp': None,
                      'resolver': None,
                      'module': self.module,
                      'source': self.source,
                      'elapse': self.elapse,
                      'find': None}
            self.results.append(result)
        else:
            for subdomain in self.subdomains:
                url = 'http://' + subdomain
                level = subdomain.count('.') - self.domain.count('.')
                info = self.infos.get(subdomain)
                if info is None:
                    info = dict()
                cname = info.get('cname')
                ip = info.get('ip')
                ip_times = info.get('ip_times')
                cname_times = info.get('cname_times')
                ttl = info.get('ttl')
                if isinstance(cname, list):
                    cname = ','.join(cname)
                    ip = ','.join(ip)
                    ip_times = ','.join([str(num) for num in ip_times])
                    cname_times = ','.join([str(num) for num in cname_times])
                    ttl = ','.join([str(num) for num in ttl])
                result = {'id': None,
                          'alive': info.get('alive'),
                          'request': info.get('request'),
                          'resolve': info.get('resolve'),
                          'url': url,
                          'subdomain': subdomain,
                          'port': 80,
                          'level': level,
                          'cname': cname,
                          'ip': ip,
                          'public': info.get('public'),
                          'cdn': info.get('cdn'),
                          'status': None,
                          'reason': info.get('reason'),
                          'title': None,
                          'banner': None,
                          'header': None,
                          'history': None,
                          'response': None,
                          'ip_times': ip_times,
                          'cname_times': cname_times,
                          'ttl': ttl,
                          'cidr': info.get('cidr'),
                          'asn': info.get('asn'),
                          'org': info.get('org'),
                          'addr': info.get('addr'),
                          'isp': info.get('isp'),
                          'resolver': info.get('resolver'),
                          'module': self.module,
                          'source': self.source,
                          'elapse': self.elapse,
                          'find': len(self.subdomains)}
                self.results.append(result)

    def save_db(self, db_path: str = None):
        """
        将模块结果保存到数据库

        :param str db_path: 数据库文件路径
        """
        logger.debug('正在保存结果到数据库')
        db = Database(db_path)
        db.create_table(self.domain)
        db.insert_many(self.domain, self.results, self.source)
        db.close()