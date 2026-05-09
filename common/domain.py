"""
域名处理模块
"""

import re
from pathlib import Path

data_config = {
    'data_dir': Path(__file__).parent.parent / 'data',
}


def set_data_config(config: dict):
    """设置域名模块全局数据配置"""
    data_config.update(config)


class Domain(object):
    """域名处理类"""

    def __init__(self, string, config: dict = None):
        """
        初始化域名处理对象

        :param str string: 输入字符串（域名或 URL）
        :param dict config: 可选配置字典
        """
        self.string = str(string)
        self.regexp = r'\b((?=[a-z0-9-]{1,63}\.)(xn--)?[a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,63}\b'
        self.domain = None
        self.config = config or {}
        self.data_dir = self.config.get('data_dir', data_config.get('data_dir'))

    def match(self):
        """
        匹配域名

        示例:
            >>> d = Domain('www.example.com')
            >>> d.match()
            'www.example.com'

        :return: 匹配的域名，未匹配返回 None
        """
        result = re.search(self.regexp, self.string, re.I)
        if result:
            return result.group()
        return None

    def extract(self):
        """
        提取域名各部分

        示例:
            >>> d = Domain('www.example.com')
            >>> d.extract()
            ExtractResult(subdomain='www', domain='example', suffix='com')

        :return: ExtractResult 包含 subdomain、domain、suffix，未提取返回 None
        """
        from common.tldextract import TLDExtract
        extract_cache_file = self.data_dir / 'public_suffix_list.dat'
        ext = TLDExtract(extract_cache_file)
        result = self.match()
        if result:
            return ext(result)
        return None

    def registered(self):
        """
        获取注册域名

        示例:
            >>> d = Domain('www.example.com')
            >>> d.registered()
            'example.com'

        :return: 注册域名（如 example.com），未提取返回 None
        """
        result = self.extract()
        if result:
            return result.registered_domain
        return None