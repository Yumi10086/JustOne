"""
SQLite 数据库初始化与操作模块
"""

import sqlite3
from pathlib import Path

from config.logging import logger

db_config = {
    'results_dir': Path(__file__).parent.parent / 'results',
}


def set_db_config(config: dict):
    """设置全局数据库配置"""
    db_config.update(config)


class Database(object):
    """数据库操作类"""

    def __init__(self, db_path=None):
        """
        初始化数据库连接

        :param str db_path: 数据库路径，默认为 None
        """
        self.conn = self.get_conn(db_path)
        self.conn.row_factory = sqlite3.Row

    @staticmethod
    def get_conn(db_path):
        """
        获取数据库连接

        :param db_path: 数据库路径
        :return: SQLite 数据库连接对象
        """
        logger.log('TRACE', '正在建立数据库连接')
        if db_path is None:
            db_path = str(db_config.get('results_dir') / 'result.sqlite3')
        logger.log('TRACE', f'使用数据库: {db_path}')
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA temp_store=MEMORY')
        return conn

    def query(self, sql, params=None):
        """
        执行查询并返回结果

        :param str sql: SQL 查询语句
        :param tuple params: 查询参数
        :return: QueryResult 包含数据和成功状态
        """
        class QueryResult:
            """查询结果包装类"""

            def __init__(self, data=None, success=True, error=None):
                self.data = data
                self.success = success
                self.error = error

            def __iter__(self):
                if self.data:
                    return iter(self.data)
                return iter([])

            def __len__(self):
                return len(self.data) if self.data else 0

            def scalar(self):
                """返回第一个值"""
                if self.data and len(self.data) > 0:
                    return self.data[0][0] if len(self.data[0]) > 0 else None
                return None

        try:
            cursor = self.conn.cursor()
            try:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                if sql.strip().upper().startswith('SELECT'):
                    results = cursor.fetchall()
                    return QueryResult(data=results)
                else:
                    self.conn.commit()
                    return QueryResult(data=cursor.rowcount, success=True)
            finally:
                cursor.close()
        except sqlite3.OperationalError as e:
            logger.log('ERROR', f'数据库操作错误: {e}')
            return QueryResult(success=False, error=str(e))
        except sqlite3.IntegrityError as e:
            logger.log('ERROR', f'数据库完整性错误: {e}')
            return QueryResult(success=False, error=str(e))
        except Exception as e:
            logger.log('ERROR', f'未知错误: {e}')
            return QueryResult(success=False, error=str(e))

    def create_table(self, table_name):
        """
        创建表

        :param str table_name: 表名
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        if self.exist_table(safe_table_name):
            logger.log('TRACE', f'表 {safe_table_name} 已存在')
            return
        logger.log('TRACE', f'正在创建表 {safe_table_name}')
        self.query(f'create table "{safe_table_name}" ('
                   f'id integer primary key,'
                   f'alive int,'
                   f'request int,'
                   f'resolve int,'
                   f'url text,'
                   f'subdomain text,'
                   f'port int,'
                   f'level int,'
                   f'cname text,'
                   f'ip text,'
                   f'public int,'
                   f'cdn int,'
                   f'status int,'
                   f'reason text,'
                   f'title text,'
                   f'banner text,'
                   f'header text,'
                   f'history text,'
                   f'response text,'
                   f'ip_times text,'
                   f'cname_times text,'
                   f'ttl text,'
                   f'cidr text,'
                   f'asn text,'
                   f'org text,'
                   f'addr text,'
                   f'isp text,'
                   f'resolver text,'
                   f'module text,'
                   f'source text,'
                   f'elapse float,'
                   f'find int)')

    def insert(self, table_name, result):
        """
        插入单条记录

        :param str table_name: 表名
        :param dict result: 要插入的记录
        :return: 查询结果
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        keys = result.keys()
        fields = ', '.join(keys)
        placeholders = ', '.join(['?' for _ in keys])
        sql = f'insert into "{safe_table_name}" ({fields}) values ({placeholders})'
        return self.query(sql, tuple(result.values()))

    def insert_many(self, table_name, results, module_name=None):
        """
        插入多条记录

        :param str table_name: 表名
        :param list results: 要插入的记录列表
        :param str module_name: 模块名称，用于日志记录
        """
        if module_name:
            logger.log('TRACE', f'正在保存 {len(results)} 条子域名结果到数据库，表名: {table_name}，模块: {module_name}')
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        if not results:
            return
        try:
            cursor = self.conn.cursor()
            try:
                keys = results[0].keys()
                fields = ', '.join(keys)
                placeholders = ', '.join(['?' for _ in keys])
                sql = f'insert into "{safe_table_name}" ({fields}) values ({placeholders})'
                for result in results:
                    cursor.execute(sql, tuple(result.values()))
                self.conn.commit()
            finally:
                cursor.close()
        except Exception as e:
            logger.log('ERROR', e)

    def save_db(self, table_name, results, module_name=None):
        """
        保存结果到数据库（insert_many 的别名，保持向后兼容）

        :param str table_name: 表名
        :param list results: 要保存的记录列表
        :param str module_name: 模块名称
        :return: insert_many 的结果
        """
        return self.insert_many(table_name, results, module_name)

    def insert_table(self, table_name, result):
        """
        插入单条记录（insert 的别名，保持向后兼容）

        :param str table_name: 表名
        :param dict result: 要插入的记录
        :return: insert 的结果
        """
        return self.insert(table_name, result)

    def exist_table(self, table_name):
        """
        判断表是否存在

        :param str table_name: 表名
        :return bool: 表是否存在
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'正在判断表 {safe_table_name} 是否存在')
        sql = 'select count() from sqlite_master where type = "table" and name = ?'
        result = self.query(sql, (safe_table_name,))
        if result.success and result.data and result.data[0][0] == 0:
            return False
        else:
            return True

    def copy_table(self, table_name, bak_table_name):
        """
        复制表以创建备份

        :param str table_name: 原表名
        :param str bak_table_name: 备份表名
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        safe_bak_name = bak_table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'正在复制表 {safe_table_name} 到新表 {safe_bak_name}')
        self.query(f'drop table if exists "{safe_bak_name}"')
        self.query(f'create table "{safe_bak_name}" '
                   f'as select * from "{safe_table_name}"')

    def clear_table(self, table_name):
        """
        清空表中的数据

        :param str table_name: 表名
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'正在清空表 {safe_table_name} 的数据')
        self.query(f'delete from "{safe_table_name}"')

    def drop_table(self, table_name):
        """
        删除表

        :param str table_name: 表名
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'正在删除表 {safe_table_name}')
        self.query(f'drop table if exists "{safe_table_name}"')

    def rename_table(self, table_name, new_table_name):
        """
        重命名表

        :param str table_name: 原表名
        :param str new_table_name: 新表名
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        safe_new_name = new_table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'正在将表 {safe_table_name} 重命名为 {safe_new_name}')
        self.query(f'alter table "{safe_table_name}" '
                   f'rename to "{safe_new_name}"')

    def deduplicate_subdomain(self, table_name):
        """
        使用 rowid 对子域名进行去重（性能更优）

        :param str table_name: 表名
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'正在对表 {safe_table_name} 中的子域名进行去重')
        self.query(f'delete from "{safe_table_name}" where '
                   f'rowid not in (select min(rowid) '
                   f'from "{safe_table_name}" group by subdomain)')

    def remove_invalid(self, table_name):
        """
        移除无效的子域名

        :param str table_name: 表名
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'正在移除表 {safe_table_name} 中的无效子域名')
        self.query(f'delete from "{safe_table_name}" where '
                   f'subdomain is null or resolve = 0')

    def get_data(self, table_name):
        """
        获取表中的所有数据

        :param str table_name: 表名
        :return: QueryResult 包含所有行
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'正在获取表 {safe_table_name} 的所有数据')
        return self.query(f'select * from "{safe_table_name}"')

    def export_data(self, table_name, alive, limit):
        """
        获取表中的部分数据

        :param str table_name: 表名
        :param any alive: 存活标志
        :param str limit: 限制值（仅支持 'resolve' 或 'request'）
        :return: 查询结果
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        sql = f'select id, alive, request, resolve, url, subdomain, level,' \
              f'cname, ip, public, cdn, port, status, reason, title, banner,' \
              f'cidr, asn, org, addr, isp, source from "{safe_table_name}" '
        params = None
        if alive and limit:
            if limit in ('resolve', 'request'):
                sql += f' where {limit} = 1'
        elif alive:
            sql += ' where alive = 1'
        sql += ' order by subdomain'
        logger.log('TRACE', f'正在从表 {safe_table_name} 获取数据')
        return self.query(sql, params)

    def count_alive(self, table_name):
        """
        统计存活的子域名数量

        :param str table_name: 表名
        :return: 存活数量
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        sql = f'select count() from "{safe_table_name}" where alive = 1'
        result = self.query(sql)
        if result.success:
            return result.scalar() or 0
        return 0

    def get_resp_by_url(self, table_name, url):
        """
        根据 URL 获取响应数据

        :param str table_name: 表名
        :param str url: URL 地址
        :return: 响应数据
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        sql = f'select response from "{safe_table_name}" where url = ?'
        logger.log('TRACE', f'正在获取 URL: {url} 的响应数据')
        result = self.query(sql, (url,))
        if result.success and result.data:
            return result.data[0][0]
        return None

    def get_data_by_fields(self, table_name, fields):
        """
        根据指定字段获取数据

        :param str table_name: 表名
        :param list fields: 字段列表
        :return: 查询结果
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        safe_fields = [f.replace('"', '') for f in fields]
        field_str = ', '.join(safe_fields)
        sql = f'select {field_str} from "{safe_table_name}"'
        logger.log('TRACE', f'正在从表 {safe_table_name} 获取指定字段 {safe_fields} 的数据')
        return self.query(sql)

    def update_data_by_url(self, table_name, info, url):
        """
        根据 URL 更新数据

        :param str table_name: 表名
        :param dict info: 要更新的信息
        :param str url: URL 地址
        :return: 查询结果
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        set_parts = [f'{k} = ?' for k in info.keys()]
        set_str = ', '.join(set_parts)
        sql = f'update "{safe_table_name}" set {set_str} where url = ?'
        params = tuple(info.values()) + (url,)
        return self.query(sql, params)

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()