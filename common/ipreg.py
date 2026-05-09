"""
IP2Region Python 搜索客户端模块
"""

import io
import socket
import struct
from pathlib import Path

ipreg_config = {
    'data_dir': Path(__file__).parent.parent / 'data',
}


def set_ipreg_config(config: dict):
    """设置全局 IP 注册配置"""
    ipreg_config.update(config)


class IpRegInfo(object):
    """IP2Region 搜索器基类"""

    __INDEX_BLOCK_LENGTH = 12
    __TOTAL_HEADER_LENGTH = 8192

    __f = None
    __headerSip = []
    __headerPtr = []
    __headerLen = 0
    __indexSPtr = 0
    __indexLPtr = 0
    __indexCount = 0
    __dbBinStr = ''

    def __init__(self, db_file):
        """
        初始化搜索器

        :param str db_file: IP 数据库文件路径
        """
        self.init_database(db_file)

    def memory_search(self, ip):
        """
        内存搜索方法

        :param ip: IP 地址或整数
        :return: IP 信息字典
        """
        if not ip.isdigit():
            ip = self.ip2long(ip)

        if self.__dbBinStr == '':
            self.__dbBinStr = self.__f.read()
            self.__indexSPtr = self.get_long(self.__dbBinStr, 0)
            self.__indexLPtr = self.get_long(self.__dbBinStr, 4)
            self.__indexCount = int((self.__indexLPtr - self.__indexSPtr) /
                                    self.__INDEX_BLOCK_LENGTH) + 1

        l, h, data_ptr = (0, self.__indexCount, 0)
        while l <= h:
            m = int((l + h) >> 1)
            p = self.__indexSPtr + m * self.__INDEX_BLOCK_LENGTH
            sip = self.get_long(self.__dbBinStr, p)

            if ip < sip:
                h = m - 1
            else:
                eip = self.get_long(self.__dbBinStr, p + 4)
                if ip > eip:
                    l = m + 1
                else:
                    data_ptr = self.get_long(self.__dbBinStr, p + 8)
                    break

        if data_ptr == 0:
            raise Exception("未找到数据指针")

        return self.return_data(data_ptr)

    def init_database(self, db_file):
        """
        初始化搜索数据库

        :param str db_file: 数据库文件路径
        """
        try:
            self.__f = io.open(db_file, "rb")
        except IOError as e:
            from config.logging import logger
            logger.error(f'打开 IP 数据库失败: {e}')
            raise

    def return_data(self, data_ptr):
        """
        根据数据指针从数据库文件获取 IP 数据

        :param data_ptr: 数据指针
        :return: IP 信息字典
        """
        data_len = (data_ptr >> 24) & 0xFF
        data_ptr = data_ptr & 0x00FFFFFF

        self.__f.seek(data_ptr)
        data = self.__f.read(data_len)

        info = {"city_id": self.get_long(data, 0),
                "region": data[4:].decode('utf-8')}
        return info

    @staticmethod
    def ip2long(ip):
        """
        将 IP 地址转换为整数

        :param ip: IP 地址字符串
        :return: 整数形式的 IP
        """
        _ip = socket.inet_aton(ip)
        return struct.unpack("!L", _ip)[0]

    @staticmethod
    def is_ip(ip):
        """
        判断字符串是否为有效的 IP 地址

        :param ip: 待检查的字符串
        :return: 是否为有效 IP
        """
        p = ip.split(".")
        if len(p) != 4:
            return False
        for pp in p:
            if not pp.isdigit():
                return False
            if len(pp) > 3:
                return False
            if int(pp) > 255:
                return False
        return True

    @staticmethod
    def get_long(b, offset):
        """
        从字节数组中提取长整数

        :param b: 字节数组
        :param offset: 偏移量
        :return: 长整数
        """
        if len(b[offset:offset + 4]) == 4:
            return struct.unpack('I', b[offset:offset + 4])[0]
        return 0

    def close(self):
        """关闭数据库文件"""
        if self.__f is not None:
            self.__f.close()
        self.__dbBinStr = None
        self.__headerPtr = None
        self.__headerSip = None


class IpRegData(IpRegInfo):
    """IP 注册数据查询类"""

    def __init__(self, config: dict = None):
        """
        初始化 IP 注册数据查询

        :param dict config: 可选配置字典
        """
        cfg = config or {}
        data_dir = cfg.get('data_dir', ipreg_config.get('data_dir'))
        path = data_dir / 'ip2region.db'
        IpRegInfo.__init__(self, path)

    def query(self, ip):
        """
        查询 IP 对应的地理位置

        :param ip: IP 地址
        :return: 包含地址和 ISP 的字典
        """
        result = self.memory_search(ip)
        addr_list = result.get('region').split('|')
        addr = ''.join(filter(lambda x: x != '0', addr_list[:-1]))
        isp = addr_list[-1]
        if isp == '0':
            isp = '未知'
        info = {'addr': addr, 'isp': isp}
        return info