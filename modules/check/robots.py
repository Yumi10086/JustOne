"""
robots.txt 文件检查模块

检查站点的 robots.txt 文件，从中匹配提取子域名
"""

from typing import Optional, Set

from common.module import Module


class Robots(Module):
    """
    robots.txt 文件检查模块

    通过访问站点的 robots.txt 文件，正则匹配其中的子域名
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 robots.txt 检查模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.domain = domain
        self.module = 'Robots'
        self.source = 'robots.txt'

    def check(self):
        """
        正则匹配域名的 robots.txt 文件中的子域
        """
        filenames = {'robots.txt'}
        self.to_check(filenames)

    def run(self) -> Set[str]:
        """
        执行 robots.txt 文件检查

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
    module = Robots(domain, config)
    return module.run()
