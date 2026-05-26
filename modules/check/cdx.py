"""
跨域策略文件检查模块

检查 crossdomain.xml 文件收集子域名
"""

from typing import Optional, Set

from common.module import Module


class CrossDomain(Module):
    """
    跨域策略文件检查模块

    通过访问站点的 crossdomain.xml 文件，从中匹配提取子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化跨域策略检查模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'CrossDomain'
        self.source = 'crossdomain.xml'

    def check(self):
        """
        检查 crossdomain.xml 收集子域名
        """
        filenames = {'crossdomain.xml'}
        self.to_check(filenames)

    def run(self) -> Set[str]:
        """
        执行跨域策略文件检查

        :return: 发现的子域名集合
        """
        self.begin()
        self.check()
        self.finish()
        self.save_json()
        self.gen_result()
        self.save_db()
        return self.subdomains


def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    """
    模块统一调用入口

    :param str domain: 目标域名
    :param dict config: 可选配置字典
    :return: 发现的子域名集合
    """
    module = CrossDomain(domain, config)
    return module.run()
