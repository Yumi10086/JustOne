"""
IP ASN 查询模块
"""

import zipfile
from pathlib import Path

from common.database import Database

ip_asn_config = {
    'data_dir': Path(__file__).parent.parent / 'data',
}


def set_ip_asn_config(config: dict):
    """设置全局 IP ASN 配置"""
    ip_asn_config.update(config)


def get_db_path(data_dir: Path = None):
    """
    获取 IP ASN 数据库路径

    :param data_dir: 数据目录路径
    :return: 数据库路径，不存在返回 None
    """
    cfg_dir = data_dir or ip_asn_config.get('data_dir')
    zip_path = cfg_dir / 'ip2location.zip'
    db_path = cfg_dir / 'ip2location.db'
    if db_path.exists():
        return db_path
    if zip_path.exists():
        zf = zipfile.ZipFile(str(zip_path))
        zf.extract('ip2location.db', cfg_dir)
        return db_path
    return None


class IPAsnInfo(Database):
    """IP ASN 信息查询类"""

    def __init__(self, db_path: str = None, config: dict = None):
        """
        初始化 IP ASN 查询

        :param str db_path: 数据库路径
        :param dict config: 可选配置字典
        """
        cfg = config or {}
        data_dir = cfg.get('data_dir', ip_asn_config.get('data_dir'))

        if db_path is None:
            db_path = get_db_path(data_dir)

        if db_path:
            Database.__init__(self, db_path)
        else:
            self.conn = None

    def find(self, ip):
        """
        查询 IP 地址的 ASN 信息

        :param ip: IP 地址
        :return: 包含 cidr、asn、org 的字典
        """
        from common.utils import ip_to_int

        info = {'cidr': '', 'asn': '', 'org': ''}
        if not self.conn:
            return info

        if isinstance(ip, (int, str)):
            ip = ip_to_int(ip)
        else:
            return info

        sql = f'SELECT * FROM asn WHERE ip_from <= {ip} AND ip_to >= {ip} LIMIT 1;'
        result = self.query(sql)
        if not result.success or len(result) == 0:
            return info

        row = result.data[0]
        info['cidr'] = row[7] if len(row) > 7 else ''
        info['asn'] = f"AS{row[2]}" if len(row) > 2 else ''
        info['org'] = row[3] if len(row) > 3 else ''
        return info


if __name__ == "__main__":
    asn_info = IPAsnInfo()
    print(asn_info.find("188.81.94.77"))