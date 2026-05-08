import zipfile
from pathlib import Path

from common.utils import ip_to_int
from config import settings
from common.database import Database


def get_db_path():
    data_dir = settings.data_dir
    zip_path = data_dir / 'ip2location.zip'
    db_path = data_dir / 'ip2location.db'
    if db_path.exists():
        return db_path
    zf = zipfile.ZipFile(str(zip_path))
    zf.extract('ip2location.db', data_dir)
    return db_path


class IPAsnInfo(Database):
    def __init__(self):
        path = get_db_path()
        Database.__init__(self, path)

    def find(self, ip):
        info = {'cidr': '', 'asn': '', 'org': ''}
        if isinstance(ip, (int, str)):
            ip = ip_to_int(ip)
        else:
            return info
        sql = f'SELECT * FROM asn WHERE ip_from <= {ip} AND ip_to >= {ip} LIMIT 1;'
        result = self.query(sql)
        if not hasattr(result, 'dataset'):
            return info
        asn = result.as_dict()
        info['cidr'] = asn[0]['cidr']
        info['asn'] = f"AS{asn[0]['asn']}"
        info['org'] = asn[0]['as']
        return info


if __name__ == "__main__":
    asn_info = IPAsnInfo()
    print(asn_info.find("188.81.94.77"))