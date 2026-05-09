"""
SQLite database initialization and operation
"""

import sqlite3
from config.logging import logger
from config import settings


class Database(object):
    def __init__(self, db_path=None):
        self.conn = self.get_conn(db_path)
        self.conn.row_factory = sqlite3.Row

    @staticmethod
    def get_conn(db_path):
        """
        Get database connection

        :param   db_path: Database path
        :return: db_conn: SQLite database connection
        """
        logger.log('TRACE', f'Establishing database connection')
        if db_path is None:
            db_path = f'{settings.result_save_dir}/result.sqlite3'
        logger.log('TRACE', f'Use the database: {db_path}')
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA temp_store=MEMORY')
        return conn

    def query(self, sql, params=None):
        """
        Execute a query and return results

        :param str sql: SQL query
        :param tuple params: Query parameters
        :return: QueryResult with data and success status
        """
        class QueryResult:
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
            logger.log('ERROR', f'Database operational error: {e}')
            return QueryResult(success=False, error=str(e))
        except sqlite3.IntegrityError as e:
            logger.log('ERROR', f'Database integrity error: {e}')
            return QueryResult(success=False, error=str(e))
        except Exception as e:
            logger.log('ERROR', f'Unexpected error: {e}')
            return QueryResult(success=False, error=str(e))

    def create_table(self, table_name):
        """
        Create table

        :param str table_name: table name
        """
        table_name = table_name.replace('.', '_')
        if self.exist_table(table_name):
            logger.log('TRACE', f'{table_name} table already exists')
            return
        logger.log('TRACE', f'Creating {table_name} table')
        self.query(f'create table "{table_name}" ('
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
        Insert a single record into the table

        :param str table_name: table name
        :param dict result: record to insert
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        keys = result.keys()
        fields = ', '.join(keys)
        placeholders = ', '.join(['?' for _ in keys])
        sql = f'insert into "{safe_table_name}" ({fields}) values ({placeholders})'
        return self.query(sql, tuple(result.values()))

    def insert_many(self, table_name, results, module_name=None):
        """
        Insert multiple records into the table

        :param str table_name: table name
        :param list results: list of records to insert
        :param str module_name: module name for logging
        """
        if module_name:
            logger.log('TRACE', f'Saving {len(results)} subdomain results of {table_name} '
                                f'found by module {module_name} to database')
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
        """Alias for insert_many for backward compatibility"""
        return self.insert_many(table_name, results, module_name)

    def insert_table(self, table_name, result):
        """Alias for insert for backward compatibility"""
        return self.insert(table_name, result)

    def exist_table(self, table_name):
        """
        Determine table exists

        :param   str table_name: table name
        :return  bool: Whether table exists
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'Determining whether the {safe_table_name} table exists')
        sql = 'select count() from sqlite_master where type = "table" and name = ?'
        result = self.query(sql, (safe_table_name,))
        if result.success and result.data and result.data[0][0] == 0:
            return False
        else:
            return True

    def copy_table(self, table_name, bak_table_name):
        """
        Copy table to create backup

        :param str table_name: table name
        :param str bak_table_name: new table name
        """
        table_name = table_name.replace('.', '_')
        bak_table_name = bak_table_name.replace('.', '_')
        logger.log('TRACE', f'Copying {table_name} table to {bak_table_name} new table')
        self.query(f'drop table if exists "{bak_table_name}"')
        self.query(f'create table "{bak_table_name}" '
                   f'as select * from "{table_name}"')

    def clear_table(self, table_name):
        """
        Clear the table

        :param str table_name: table name
        """
        table_name = table_name.replace('.', '_')
        logger.log('TRACE', f'Clearing data in table {table_name}')
        self.query(f'delete from "{table_name}"')

    def drop_table(self, table_name):
        """
        Delete table

        :param str table_name: table name
        """
        table_name = table_name.replace('.', '_')
        logger.log('TRACE', f'Deleting {table_name} table')
        self.query(f'drop table if exists "{table_name}"')

    def rename_table(self, table_name, new_table_name):
        """
        Rename table name

        :param str table_name: old table name
        :param str new_table_name: new table name
        """
        table_name = table_name.replace('.', '_')
        new_table_name = new_table_name.replace('.', '_')
        logger.log('TRACE', f'Renaming {table_name} table to {new_table_name} table')
        self.query(f'alter table "{table_name}" '
                   f'rename to "{new_table_name}"')

    def deduplicate_subdomain(self, table_name):
        """
        Deduplicate subdomains in the table using rowid for better performance

        :param str table_name: table name
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'Deduplicating subdomains in {safe_table_name} table')
        self.query(f'delete from "{safe_table_name}" where '
                   f'rowid not in (select min(rowid) '
                   f'from "{safe_table_name}" group by subdomain)')

    def remove_invalid(self, table_name):
        """
        Remove nulls or invalid subdomains in the table

        :param str table_name: table name
        """
        table_name = table_name.replace('.', '_')
        logger.log('TRACE', f'Removing invalid subdomains in {table_name} table')
        self.query(f'delete from "{table_name}" where '
                   f'subdomain is null or resolve = 0')

    def get_data(self, table_name):
        """
        Get all the data in the table

        :param str table_name: table name
        :return: QueryResult with all rows
        """
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        logger.log('TRACE', f'Get all the data from {safe_table_name} table')
        return self.query(f'select * from "{safe_table_name}"')

    def export_data(self, table_name, alive, limit):
        """
        Get part of the data in the table

        :param str table_name: table name
        :param any alive: alive flag
        :param str limit: limit value (only 'resolve' or 'request' allowed)
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
        logger.log('TRACE', f'Get the data from {safe_table_name} table')
        return self.query(sql, params)

    def count_alive(self, table_name):
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        sql = f'select count() from "{safe_table_name}" where alive = 1'
        result = self.query(sql)
        if result.success:
            return result.scalar() or 0
        return 0

    def get_resp_by_url(self, table_name, url):
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        sql = f'select response from "{safe_table_name}" where url = ?'
        logger.log('TRACE', f'Get response data from {url}')
        result = self.query(sql, (url,))
        if result.success and result.data:
            return result.data[0][0]
        return None

    def get_data_by_fields(self, table_name, fields):
        safe_table_name = table_name.replace('.', '_').replace('"', '')
        safe_fields = [f.replace('"', '') for f in fields]
        field_str = ', '.join(safe_fields)
        sql = f'select {field_str} from "{safe_table_name}"'
        logger.log('TRACE', f'Get specified field data {safe_fields} from {safe_table_name} table')
        return self.query(sql)

    def update_data_by_url(self, table_name, info, url):
        table_name = table_name.replace('.', '_')
        set_parts = [f'{k} = ?' for k in info.keys()]
        set_str = ', '.join(set_parts)
        sql = f'update "{table_name}" set {set_str} where url = ?'
        params = tuple(info.values()) + (url,)
        return self.query(sql, params)

    def close(self):
        """
        Close the database connection
        """
        if self.conn:
            self.conn.close()