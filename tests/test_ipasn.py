"""
Unit tests for common/ipasn.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import unittest
from unittest.mock import patch, MagicMock
from common.ipasn import IPAsnInfo, ip_asn_config, set_ip_asn_config, get_db_path


class TestIPAsnConfig(unittest.TestCase):
    def setUp(self):
        self.original_config = ip_asn_config.copy()

    def tearDown(self):
        ip_asn_config.update(self.original_config)

    def test_default_config(self):
        """Test default config has data_dir"""
        self.assertIn('data_dir', ip_asn_config)
        self.assertIsInstance(ip_asn_config['data_dir'], Path)

    def test_set_ip_asn_config(self):
        """Test set_ip_asn_config updates config"""
        new_dir = Path('/new/data')
        set_ip_asn_config({'data_dir': new_dir})
        self.assertEqual(ip_asn_config['data_dir'], new_dir)


class TestGetDbPath(unittest.TestCase):
    @patch('pathlib.Path.exists')
    def test_get_db_path_existing(self, mock_exists):
        """Test get_db_path returns existing db"""
        mock_exists.return_value = True
        db_path = get_db_path(Path('/test/data'))
        self.assertIsNotNone(db_path)
        self.assertIn('ip2location.db', str(db_path))

    @patch('pathlib.Path.exists')
    def test_get_db_path_no_file(self, mock_exists):
        """Test get_db_path returns None when no files exist"""
        mock_exists.return_value = False
        db_path = get_db_path(Path('/nonexistent'))
        self.assertIsNone(db_path)


class TestIPAsnInfo(unittest.TestCase):
    def test_find_no_conn(self):
        """Test find returns empty info when no connection"""
        asn = IPAsnInfo.__new__(IPAsnInfo)
        asn.conn = None
        result = asn.find('8.8.8.8')
        self.assertEqual(result, {'cidr': '', 'asn': '', 'org': ''})

    @patch('common.database.Database.__init__')
    def test_init_with_none_db_path(self, mock_init):
        """Test IPAsnInfo handles None db_path"""
        mock_init.return_value = None
        asn = IPAsnInfo(db_path=None, config={'data_dir': Path('/test')})
        self.assertIsNotNone(asn)

    @patch('common.database.Database.query')
    @patch('common.database.Database.__init__')
    def test_find_with_result(self, mock_init, mock_query):
        """Test find returns result when query succeeds"""
        mock_init.return_value = None

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = [('192.168.1.0', '192.168.1.255', 12345, 'Example Org', '', '', '', '192.168.1.0/24')]
        mock_result.__len__ = lambda self: 1
        mock_query.return_value = mock_result

        asn = IPAsnInfo(db_path=':memory:')
        asn.conn = MagicMock()
        result = asn.find('192.168.1.100')

        self.assertIn('cidr', result)
        self.assertIn('asn', result)
        self.assertIn('org', result)


if __name__ == '__main__':
    unittest.main()