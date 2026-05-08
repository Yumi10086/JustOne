"""
Module base class
"""

import json
import threading
import time

import requests
from config.logging import logger
from config import settings
from common import utils
from common.database import Database

lock = threading.Lock()


class Module(object):
    def __init__(self):
        self.module = 'Module'
        self.source = 'BaseModule'
        self.cookie = None
        self.header = dict()
        self.proxy = None
        self.delay = 1
        self.timeout = settings.http_timeout
        self.verify = settings.http_verify_ssl
        self.domain = str()
        self.subdomains = set()
        self.infos = dict()
        self.results = list()
        self.start = time.time()
        self.end = None
        self.elapse = None

    def have_api(self, *apis):
        """
        Simply check whether the api information configure or not

        :param  apis: apis set
        :return bool: check result
        """
        if not all(apis):
            logger.debug(f'{self.source} module is not configured')
            return False
        return True

    def begin(self):
        """
        begin log
        """
        logger.debug(f'Start {self.source} module to '
                    f'collect subdomains of {self.domain}')

    def finish(self):
        """
        finish log
        """
        self.end = time.time()
        self.elapse = round(self.end - self.start, 1)
        logger.debug(f'Finished {self.source} module to '
                    f'collect {self.domain}\'s subdomains')
        logger.info(f'{self.source} module took {self.elapse} seconds '
                    f'found {len(self.subdomains)} subdomains')
        logger.debug(f'{self.source} module found subdomains of {self.domain}\n'
                    f'{self.subdomains}')

    def head(self, url, params=None, check=True, **kwargs):
        """
        Custom head request

        :param str  url: request url
        :param dict params: request parameters
        :param bool check: check response
        :param kwargs: other params
        :return: response object
        """
        session = requests.Session()
        session.trust_env = False
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
            logger.error(e.args[0])
            return None
        if not check:
            return resp
        if utils.check_response('HEAD', resp):
            return resp
        return None

    def get(self, url, params=None, check=True, ignore=False, raise_error=False, **kwargs):
        """
        Custom get request

        :param str  url: request url
        :param dict params: request parameters
        :param bool check: check response
        :param bool ignore: ignore error
        :param bool raise_error: raise error or not
        :param kwargs: other params
        :return: response object
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
        Custom post request

        :param str  url: request url
        :param dict data: request data
        :param bool check: check response
        :param kwargs: other params
        :return: response object
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
        Custom delete request

        :param str  url: request url
        :param bool check: check response
        :param kwargs: other params
        :return: response object
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
        Get request header

        :return: header
        """
        headers = utils.gen_fake_header()
        if isinstance(headers, dict):
            self.header = headers
            return headers
        return self.header

    def get_proxy(self, module):
        """
        Get proxy

        :param str module: module name
        :return: proxy
        """
        if not settings.proxy_enable:
            logger.debug(f'All modules do not use proxy')
            return self.proxy
        logger.debug(f'{module} module uses proxy')
        return utils.get_random_proxy()

    def match_subdomains(self, resp, distinct=True, fuzzy=True):
        if not resp:
            return set()
        elif isinstance(resp, str):
            return utils.match_subdomains(self.domain, resp, distinct, fuzzy)
        elif hasattr(resp, 'text'):
            return utils.match_subdomains(self.domain, resp.text, distinct, fuzzy)
        else:
            return set()

    def collect_subdomains(self, resp):
        subdomains = self.match_subdomains(resp)
        self.subdomains.update(subdomains)
        return self.subdomains

    def save_json(self):
        """
        Save the results of each module as a json file

        :return bool: whether saved successfully
        """
        if not settings.collect_save_module_result:
            return False
        logger.debug(f'Save the subdomain results found by '
                    f'{self.source} module as a json file')
        path = settings.results_dir / self.domain / self.module
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
        """
        Generate results
        """
        logger.debug(f'Generating final results')
        if not len(self.subdomains):
            logger.debug(f'{self.source} module result is empty')
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

    def save_db(self):
        """
        Save module results into the database
        """
        logger.debug(f'Saving results to database')
        lock.acquire()
        db = Database()
        db.create_table(self.domain)
        db.save_db(self.domain, self.results, self.source)
        db.close()
        lock.release()