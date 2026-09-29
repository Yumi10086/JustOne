"""
Unit tests for common/database.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import unittest
import os
import tempfile
from common.database import Database


class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, 'test.db')

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.db = Database(self.db_path)
        self.db.create_table('test_table')

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_table(self):
        self.assertTrue(self.db.exist_table('test_table'))

    def test_exist_table_false(self):
        self.assertFalse(self.db.exist_table('nonexistent_table'))

    def test_insert_single(self):
        result = {
            'id': 1,
            'subdomain': 'test.example.com',
            'resolve': 1,
            'alive': 1
        }
        query_result = self.db.insert('test_table', result)
        self.assertTrue(query_result.success)

        data = self.db.get_data('test_table')
        self.assertEqual(len(data), 1)
        self.assertEqual(data.data[0]['subdomain'], 'test.example.com')

    def test_insert_many(self):
        results = [
            {'id': 1, 'subdomain': 'a.example.com', 'resolve': 1, 'alive': 0},
            {'id': 2, 'subdomain': 'b.example.com', 'resolve': 1, 'alive': 1},
            {'id': 3, 'subdomain': 'c.example.com', 'resolve': 0, 'alive': 0},
        ]
        self.db.insert_many('test_table', results, 'test_module')
        data = self.db.get_data('test_table')
        self.assertEqual(len(data), 3)

    def test_count_alive(self):
        results = [
            {'id': 1, 'subdomain': 'a.example.com', 'alive': 1},
            {'id': 2, 'subdomain': 'b.example.com', 'alive': 0},
            {'id': 3, 'subdomain': 'c.example.com', 'alive': 1},
        ]
        self.db.insert_many('test_table', results)
        count = self.db.count_alive('test_table')
        self.assertEqual(count, 2)

    def test_count_alive_empty(self):
        count = self.db.count_alive('test_table')
        self.assertEqual(count, 0)

    def test_deduplicate_subdomain(self):
        results = [
            {'id': 1, 'subdomain': 'dup.example.com', 'resolve': 1, 'alive': 1},
            {'id': 2, 'subdomain': 'dup.example.com', 'resolve': 1, 'alive': 1},
            {'id': 3, 'subdomain': 'unique.example.com', 'resolve': 1, 'alive': 1},
        ]
        self.db.insert_many('test_table', results)
        self.db.deduplicate_subdomain('test_table')
        data = self.db.get_data('test_table')
        self.assertEqual(len(data), 2)

    def test_remove_invalid(self):
        results = [
            {'id': 1, 'subdomain': 'valid.example.com', 'resolve': 1, 'alive': 1},
            {'id': 2, 'subdomain': 'invalid.example.com', 'resolve': 0, 'alive': 1},
            {'id': 3, 'subdomain': None, 'resolve': 1, 'alive': 1},
        ]
        self.db.insert_many('test_table', results)
        self.db.remove_invalid('test_table')
        data = self.db.get_data('test_table')
        self.assertEqual(len(data), 1)
        self.assertEqual(data.data[0]['subdomain'], 'valid.example.com')

    def test_export_data_all(self):
        results = [
            {'id': 1, 'subdomain': 'a.example.com', 'alive': 1, 'resolve': 1, 'request': 1, 'url': 'http://a.example.com', 'level': 1, 'cname': '', 'ip': '1.1.1.1', 'public': 1, 'cdn': 0, 'port': 80, 'status': 200, 'reason': 'ok', 'title': 'Test', 'banner': '', 'cidr': '', 'asn': '', 'org': '', 'addr': '', 'isp': '', 'source': 'test'},
            {'id': 2, 'subdomain': 'b.example.com', 'alive': 0, 'resolve': 1, 'request': 0, 'url': 'http://b.example.com', 'level': 1, 'cname': '', 'ip': '2.2.2.2', 'public': 1, 'cdn': 0, 'port': 80, 'status': 0, 'reason': 'timeout', 'title': '', 'banner': '', 'cidr': '', 'asn': '', 'org': '', 'addr': '', 'isp': '', 'source': 'test'},
        ]
        self.db.insert_many('test_table', results)
        data = self.db.export_data('test_table', alive=False, limit=None)
        self.assertEqual(len(data), 2)

    def test_export_data_alive_only(self):
        results = [
            {'id': 1, 'subdomain': 'a.example.com', 'alive': 1, 'resolve': 1, 'request': 1, 'url': 'http://a.example.com', 'level': 1, 'cname': '', 'ip': '1.1.1.1', 'public': 1, 'cdn': 0, 'port': 80, 'status': 200, 'reason': 'ok', 'title': 'Test', 'banner': '', 'cidr': '', 'asn': '', 'org': '', 'addr': '', 'isp': '', 'source': 'test'},
            {'id': 2, 'subdomain': 'b.example.com', 'alive': 0, 'resolve': 1, 'request': 0, 'url': 'http://b.example.com', 'level': 1, 'cname': '', 'ip': '2.2.2.2', 'public': 1, 'cdn': 0, 'port': 80, 'status': 0, 'reason': 'timeout', 'title': '', 'banner': '', 'cidr': '', 'asn': '', 'org': '', 'addr': '', 'isp': '', 'source': 'test'},
        ]
        self.db.insert_many('test_table', results)
        data = self.db.export_data('test_table', alive=True, limit=None)
        self.assertEqual(len(data), 1)
        self.assertEqual(data.data[0]['subdomain'], 'a.example.com')

    def test_export_data_limit_resolve(self):
        results = [
            {'id': 1, 'subdomain': 'a.example.com', 'alive': 1, 'resolve': 1, 'request': 0, 'url': 'http://a.example.com', 'level': 1, 'cname': '', 'ip': '1.1.1.1', 'public': 1, 'cdn': 0, 'port': 80, 'status': 0, 'reason': 'ok', 'title': '', 'banner': '', 'cidr': '', 'asn': '', 'org': '', 'addr': '', 'isp': '', 'source': 'test'},
            {'id': 2, 'subdomain': 'b.example.com', 'alive': 0, 'resolve': 0, 'request': 0, 'url': 'http://b.example.com', 'level': 1, 'cname': '', 'ip': '', 'public': 1, 'cdn': 0, 'port': 80, 'status': 0, 'reason': 'ok', 'title': '', 'banner': '', 'cidr': '', 'asn': '', 'org': '', 'addr': '', 'isp': '', 'source': 'test'},
        ]
        self.db.insert_many('test_table', results)
        data = self.db.export_data('test_table', alive=True, limit='resolve')
        self.assertEqual(len(data), 1)

    def test_clear_table(self):
        results = [
            {'id': 1, 'subdomain': 'a.example.com', 'alive': 1},
            {'id': 2, 'subdomain': 'b.example.com', 'alive': 1},
        ]
        self.db.insert_many('test_table', results)
        self.db.clear_table('test_table')
        data = self.db.get_data('test_table')
        self.assertEqual(len(data), 0)

    def test_drop_table(self):
        self.assertTrue(self.db.exist_table('test_table'))
        self.db.drop_table('test_table')
        self.assertFalse(self.db.exist_table('test_table'))

    def test_copy_table(self):
        results = [
            {'id': 1, 'subdomain': 'a.example.com', 'alive': 1},
        ]
        self.db.insert_many('test_table', results)
        self.db.copy_table('test_table', 'backup_table')
        self.assertTrue(self.db.exist_table('backup_table'))
        data = self.db.get_data('backup_table')
        self.assertEqual(len(data), 1)

    def test_rename_table(self):
        self.db.rename_table('test_table', 'new_table')
        self.assertFalse(self.db.exist_table('test_table'))
        self.assertTrue(self.db.exist_table('new_table'))

    def test_update_data_by_url(self):
        results = [
            {'id': 1, 'subdomain': 'a.example.com', 'alive': 1, 'url': 'http://a.example.com', 'title': ''},
        ]
        self.db.insert_many('test_table', results)
        self.db.update_data_by_url('test_table', {'title': 'Updated', 'alive': 0}, 'http://a.example.com')
        data = self.db.get_data('test_table')
        self.assertEqual(data.data[0]['title'], 'Updated')
        self.assertEqual(data.data[0]['alive'], 0)

    def test_query_result_iteration(self):
        results = [
            {'id': 1, 'subdomain': 'a.example.com'},
            {'id': 2, 'subdomain': 'b.example.com'},
        ]
        self.db.insert_many('test_table', results)
        data = self.db.get_data('test_table')
        count = 0
        for row in data:
            count += 1
        self.assertEqual(count, 2)

    def test_query_result_scalar(self):
        self.db.insert('test_table', {'id': 1, 'subdomain': 'a.example.com'})
        result = self.db.query('select count() from "test_table"')
        self.assertEqual(result.scalar(), 1)

    def test_backward_compatibility_insert_table(self):
        result = {'id': 1, 'subdomain': 'test.com'}
        self.db.insert_table('test_table', result)
        data = self.db.get_data('test_table')
        self.assertEqual(len(data), 1)

    def test_backward_compatibility_save_db(self):
        results = [{'id': 1, 'subdomain': 'test.com'}]
        self.db.save_db('test_table', results, 'test_module')
        data = self.db.get_data('test_table')
        self.assertEqual(len(data), 1)

    def test_table_name_sanitization(self):
        self.db.insert('test.table', {'id': 1, 'subdomain': 'test.com'})
        self.assertTrue(self.db.exist_table('test_table'))

    def test_sql_injection_prevention(self):
        self.db.insert('test_table', {'id': 1, 'subdomain': 'test.com'})
        self.db.insert('test_table', {'id': 2, 'subdomain': 'test"; DROP TABLE test_table; --'})
        data = self.db.get_data('test_table')
        self.assertEqual(len(data), 2)
        self.assertTrue(self.db.exist_table('test_table'))


if __name__ == '__main__':
    unittest.main()