"""
crts.sh 证书查询模块
"""

import json
from typing import Optional, Set

from common.module import Module
from common import utils


class Crtsh(Module):
    """
    crts.sh 证书透明度查询模块

    通过查询 crts.sh 获取目标域名的证书信息
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        初始化 crts.sh 模块

        :param str domain: 目标域名
        :param dict config: 可选配置字典
        """
        super().__init__(domain, config)
        self.module = 'Crtsh'
        self.source = 'crts.sh'

    def run(self) -> Set[str]:
        """
        执行 crts.sh 证书查询

        :return: 发现的子域名集合
        """
        self.begin()
        logger = utils.get_logger()

        try:
            url = 'https://crt.sh/'
            params = {
                'q': f'.{self.domain}',
                'output': 'json',
            }
            resp = self.get(url, params=params, timeout=60)
            if resp and resp.text:
                data = json.loads(resp.text)
                for item in data:
                    name_value = item.get('name_value', '')
                    subdomains = self.match_subdomains(name_value, distinct=True, fuzzy=True)
                    self.subdomains.update(subdomains)
                logger.info(f'crts.sh 查询完成，发现 {len(self.subdomains)} 个子域名')
        except Exception as e:
            logger.error(f'crts.sh 查询出错: {e}')

        self.finish()
        return self.subdomains