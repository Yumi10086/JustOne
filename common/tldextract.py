# -*- coding: utf-8 -*-
"""
TLD 提取模块

准确地将 gTLD 或 ccTLD（通用顶级域名或国家代码顶级域名）从 URL 的注册域名和子域名中分离出来。

    >>> import tldextract

    >>> tldextract.extract('http://forums.news.cnn.com/')
    ExtractResult(subdomain='forums.news', domain='cnn', suffix='com')

    >>> tldextract.extract('http://forums.bbc.co.uk/') # 英国
    ExtractResult(subdomain='forums', domain='bbc', suffix='co.uk')

    >>> tldextract.extract('http://www.worldbank.org.kg/') # 吉尔吉斯斯坦
    ExtractResult(subdomain='www', domain='worldbank', suffix='org.kg')

`ExtractResult` 是一个 namedtuple，可以轻松访问各个部分。

    >>> ext = tldextract.extract('http://forums.bbc.co.uk')
    >>> (ext.subdomain, ext.domain, ext.suffix)
    ('forums', 'bbc', 'co.uk')
    >>> # 重新组合子域名和域名
    >>> '.'.join(ext[:2])
    'forums.bbc'
    >>> # 常用别名
    >>> ext.registered_domain
    'bbc.co.uk'

注意子域名和后缀是可选的。并非所有类似 URL 的输入都有子域名或有效的后缀。

    >>> tldextract.extract('google.com')
    ExtractResult(subdomain='', domain='google', suffix='com')

    >>> tldextract.extract('google.notavalidsuffix')
    ExtractResult(subdomain='google', domain='notavalidsuffix', suffix='')

    >>> tldextract.extract('http://127.0.0.1:8080/deployed/')
    ExtractResult(subdomain='', domain='127.0.0.1', suffix='')

如果要重新组合整个 namedtuple，无论是否找到子域名或后缀：

    >>> ext = tldextract.extract('http://127.0.0.1:8080/deployed/')
    >>> # 这会有多余的点
    >>> '.'.join(ext)
    '.127.0.0.1.'
"""


import os
import re
import json
import collections
import socket
from urllib.parse import scheme_chars
from functools import wraps

import idna
import socket

IP_RE = re.compile(r'^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$')  # pylint: disable=line-too-long

SCHEME_RE = re.compile(r'^([' + scheme_chars + ']+:)?//')


class ExtractResult(collections.namedtuple('ExtractResult', 'subdomain domain suffix')):
    """URL 的子域名、域名和后缀的 namedtuple"""

    # Necessary for __dict__ member to get populated in Python 3+
    __slots__ = ()

    @property
    def registered_domain(self):
        """
        如果域名和后缀都设置了，用点号连接起来

        >>> extract('http://forums.bbc.co.uk').registered_domain
        'bbc.co.uk'
        >>> extract('http://localhost:8080').registered_domain
        ''
        """
        if self.domain and self.suffix:
            return self.domain + '.' + self.suffix
        return ''

    @property
    def fqdn(self):
        """
        Returns a Fully Qualified Domain Name, if there is a proper domain/suffix.

        >>> extract('http://forums.bbc.co.uk/path/to/file').fqdn
        'forums.bbc.co.uk'
        >>> extract('http://localhost:8080').fqdn
        ''
        """
        if self.domain and self.suffix:
            # self is the namedtuple (subdomain domain suffix)
            return '.'.join(i for i in self if i)
        return ''

    @property
    def ipv4(self):
        """
        Returns the ipv4 if that is what the presented domain/url is

        >>> extract('http://127.0.0.1/path/to/file').ipv4
        '127.0.0.1'
        >>> extract('http://127.0.0.1.1/path/to/file').ipv4
        ''
        >>> extract('http://256.1.1.1').ipv4
        ''
        """
        if not (self.suffix or self.subdomain) and IP_RE.match(self.domain):
            return self.domain
        return ''


class TLDExtract(object):
    """A callable for extracting, subdomain, domain, and suffix components from a URL."""

    def __init__(self, cache_file=None):
        """
        Constructs a callable for extracting subdomain, domain, and suffix
        components from a URL.
        """

        self.cache_file = os.path.expanduser(cache_file or '')
        self._extractor = None

    def __call__(self, url):
        """
        Takes a string URL and splits it into its subdomain, domain, and
        suffix (effective TLD, gTLD, ccTLD, etc.) component.

        >>> ext = TLDExtract()
        >>> ext('http://forums.news.cnn.com/')
        ExtractResult(subdomain='forums.news', domain='cnn', suffix='com')
        >>> ext('http://forums.bbc.co.uk/')
        ExtractResult(subdomain='forums', domain='bbc', suffix='co.uk')
        """
        netloc = SCHEME_RE.sub("", url) \
            .partition("/")[0] \
            .partition("?")[0] \
            .partition("#")[0] \
            .split("@")[-1] \
            .partition(":")[0] \
            .strip() \
            .rstrip(".")

        labels = netloc.split(".")

        translations = [_decode_punycode(label) for label in labels]
        suffix_index = self._get_tld_extractor().suffix_index(translations)

        suffix = ".".join(labels[suffix_index:])
        if not suffix and netloc and _looks_like_ip(netloc):
            return ExtractResult('', netloc, '')

        subdomain = ".".join(labels[:suffix_index - 1]) if suffix_index else ""
        domain = labels[suffix_index - 1] if suffix_index else ""
        # 简单的 IP 检测
        if not subdomain and not suffix and IP_RE.match(netloc):
            return ExtractResult('', netloc, '')
        return ExtractResult(subdomain, domain, suffix)

    @property
    def tlds(self):
        return self._get_tld_extractor().tlds

    def _get_tld_extractor(self):
        """Get or compute this object's TLDExtractor. Looks up the TLDExtractor
        in roughly the following order, based on the settings passed to
        __init__:

        1. Memoized on `self`
        2. Local system cache file"""
        # pylint: disable=no-else-return

        if self._extractor:
            return self._extractor
        tlds = self._get_cached_tlds()
        if tlds:
            self._extractor = _PublicSuffixListTLDExtractor(tlds)
            return self._extractor
        else:
            raise Exception("tlds is empty, cannot proceed without tlds.")

    def _get_cached_tlds(self):
        """Read the local TLD cache file. Returns None on IOError or other
        error, or if this object is not set to use the cache
        file."""
        if not self.cache_file:
            return None

        with open(self.cache_file) as cache_file:
            return json.loads(cache_file.read())


TLD_EXTRACTOR = TLDExtract()


@wraps(TLD_EXTRACTOR.__call__)
def extract(url):
    return TLD_EXTRACTOR(url)


class _PublicSuffixListTLDExtractor(object):
    """Wrapper around this project's main algo for PSL
    lookups.
    """
    def __init__(self, tlds):
        self.tlds = frozenset(tlds)

    def suffix_index(self, lower_spl):
        """Returns the index of the first suffix label.
        Returns len(spl) if no suffix is found
        """
        length = len(lower_spl)
        for i in range(length):
            maybe_tld = '.'.join(lower_spl[i:])
            exception_tld = '!' + maybe_tld
            if exception_tld in self.tlds:
                return i + 1

            if maybe_tld in self.tlds:
                return i

            wildcard_tld = '*.' + '.'.join(lower_spl[i + 1:])
            if wildcard_tld in self.tlds:
                return i

        return length


def _looks_like_ip(maybe_ip):
    """判断是否为 IP 地址"""
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
    return False


def _decode_punycode(label):
    lowered = label.lower()
    looks_like_puny = lowered.startswith('xn--')
    if looks_like_puny:
        try:
            return idna.decode(label.encode('ascii')).lower()
        except (UnicodeError, IndexError):
            pass
    return lowered
