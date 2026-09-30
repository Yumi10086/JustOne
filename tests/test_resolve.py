"""
Unit tests for common/resolve.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import unittest
from unittest.mock import patch, MagicMock
from common.resolve import (
    filter_subdomain,
    update_data,
    resolve_domain,
    resolve_batch,
    run_resolve,
    resolve_config,
    set_resolve_config,
)


class TestResolveConfig(unittest.TestCase):
    def setUp(self):
        self.original_config = resolve_config.copy()

    def tearDown(self):
        resolve_config.update(self.original_config)

    def test_default_config(self):
        """Test default config values"""
        self.assertIn('project_root', resolve_config)
        self.assertIn('results_dir', resolve_config)
        self.assertIn('dns_nameservers', resolve_config)
        self.assertIsInstance(resolve_config['dns_nameservers'], list)

    def test_set_resolve_config(self):
        """Test set_resolve_config updates config"""
        new_config = {'dns_nameservers': ['8.8.8.8'], 'custom_key': 'value'}
        set_resolve_config(new_config)
        self.assertEqual(resolve_config['dns_nameservers'], ['8.8.8.8'])
        self.assertEqual(resolve_config['custom_key'], 'value')

    def test_set_resolve_config_preserves_others(self):
        """Test set_resolve_config preserves other values"""
        original_project_root = resolve_config['project_root']
        set_resolve_config({'dns_nameservers': ['1.1.1.1']})
        self.assertEqual(resolve_config['project_root'], original_project_root)


class TestFilterSubdomain(unittest.TestCase):
    def test_filter_with_ip(self):
        """Test filter returns subdomains without IP"""
        data = [
            {'subdomain': 'a.com', 'ip': '1.1.1.1'},
            {'subdomain': 'b.com', 'ip': ''},
            {'subdomain': 'c.com'},
        ]
        result = filter_subdomain(data)
        self.assertEqual(set(result), {'b.com', 'c.com'})

    def test_filter_all_have_ip(self):
        """Test filter returns empty when all have IP"""
        data = [
            {'subdomain': 'a.com', 'ip': '1.1.1.1'},
            {'subdomain': 'b.com', 'ip': '2.2.2.2'},
        ]
        result = filter_subdomain(data)
        self.assertEqual(result, [])

    def test_filter_empty_data(self):
        """Test filter with empty data"""
        result = filter_subdomain([])
        self.assertEqual(result, [])

    def test_filter_missing_subdomain(self):
        """Test filter handles missing subdomain key"""
        data = [
            {'ip': '1.1.1.1'},
            {'subdomain': 'b.com'},
        ]
        result = filter_subdomain(data)
        self.assertEqual(result, ['b.com'])


class TestUpdateData(unittest.TestCase):
    def test_update_with_infos(self):
        """Test update_data merges infos"""
        data = [
            {'subdomain': 'a.com', 'ip': ''},
            {'subdomain': 'b.com', 'ip': ''},
        ]
        infos = {
            'a.com': {'ip': '1.1.1.1', 'resolve': 1},
            'b.com': {'ip': '2.2.2.2', 'resolve': 1},
        }
        result = update_data(data, infos)
        self.assertEqual(result[0]['ip'], '1.1.1.1')
        self.assertEqual(result[1]['ip'], '2.2.2.2')

    def test_update_keeps_existing_ip(self):
        """Test update_data keeps existing IP"""
        data = [
            {'subdomain': 'a.com', 'ip': '1.1.1.1'},
            {'subdomain': 'b.com', 'ip': ''},
        ]
        infos = {'b.com': {'ip': '2.2.2.2', 'resolve': 1}}
        result = update_data(data, infos)
        self.assertEqual(result[0]['ip'], '1.1.1.1')
        self.assertEqual(result[1]['ip'], '2.2.2.2')

    def test_update_empty_infos(self):
        """Test update_data with empty infos"""
        data = [{'subdomain': 'a.com'}]
        result = update_data(data, {})
        self.assertEqual(result, data)

    def test_update_no_match(self):
        """Test update_data when no infos match - unmatched items are kept"""
        data = [{'subdomain': 'a.com', 'ip': ''}, {'subdomain': 'b.com', 'ip': '1.1.1.1'}]
        infos = {'c.com': {'ip': '2.2.2.2'}}
        result = update_data(data, infos)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['subdomain'], 'b.com')


class TestResolveDomain(unittest.TestCase):
    def setUp(self):
        # _get_resolver 按线程缓存 Resolver，重置缓存确保每个用例使用新的 mock
        import threading
        from common import resolve as resolve_module
        resolve_module._resolver_local = threading.local()

    @patch('dns.resolver.Resolver')
    def test_resolve_success(self, mock_resolver_class):
        """Test successful domain resolution"""
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver

        mock_a_record = MagicMock()
        mock_a_record.__str__ = lambda self: '1.1.1.1'
        mock_resolver.resolve.return_value = [mock_a_record]

        result = resolve_domain('example.com')
        self.assertIsNotNone(result)
        self.assertEqual(result['resolve'], 1)

    @patch('dns.resolver.Resolver')
    def test_resolve_nxdomain(self, mock_resolver_class):
        """Test resolution returns NXDOMAIN"""
        import dns.resolver
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        result = resolve_domain('nonexistent.example.com')
        self.assertEqual(result['reason'], 'NXDOMAIN')

    @patch('dns.resolver.Resolver')
    def test_resolve_timeout(self, mock_resolver_class):
        """Test resolution timeout"""
        import dns.exception
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.exception.Timeout()

        result = resolve_domain('timeout.example.com')
        self.assertEqual(result['reason'], 'Timeout')


class TestResolveBatch(unittest.TestCase):
    @patch('common.resolve.resolve_domain')
    def test_resolve_batch(self, mock_resolve_domain):
        """Test batch resolution"""
        mock_resolve_domain.side_effect = [
            {'subdomain': 'a.com', 'resolve': 1, 'ip': '1.1.1.1'},
            {'subdomain': 'b.com', 'resolve': 0, 'reason': 'NXDOMAIN'},
        ]

        result = resolve_batch(['a.com', 'b.com'])
        self.assertEqual(len(result), 2)
        self.assertIn('a.com', result)
        self.assertIn('b.com', result)

    @patch('common.resolve.resolve_domain')
    def test_resolve_batch_with_progress(self, mock_resolve_domain):
        """Test batch resolution with progress callback"""
        mock_resolve_domain.return_value = {'resolve': 1}

        progress_calls = []
        def progress_callback(current, total):
            progress_calls.append((current, total))

        resolve_batch(['a.com', 'b.com', 'c.com'], progress_callback=progress_callback)
        self.assertEqual(len(progress_calls), 3)
        self.assertEqual(progress_calls[-1], (3, 3))


class TestRunResolve(unittest.TestCase):
    @patch('common.resolve.resolve_batch')
    def test_run_resolve(self, mock_resolve_batch):
        """Test run_resolve"""
        mock_resolve_batch.return_value = {
            'sub1.com': {'ip': '1.1.1.1', 'resolve': 1},
        }

        data = [
            {'subdomain': 'sub1.com', 'ip': ''},
            {'subdomain': 'sub2.com', 'ip': '2.2.2.2'},
        ]

        result = run_resolve('example.com', data)
        self.assertEqual(result[0]['ip'], '1.1.1.1')
        self.assertEqual(result[1]['ip'], '2.2.2.2')

    def test_run_resolve_no_subdomains(self):
        """Test run_resolve with no subdomains to resolve"""
        data = [
            {'subdomain': 'sub1.com', 'ip': '1.1.1.1'},
            {'subdomain': 'sub2.com', 'ip': '2.2.2.2'},
        ]

        result = run_resolve('example.com', data)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ip'], '1.1.1.1')


class TestNsPool(unittest.TestCase):
    def test_pool_contains_builtin_and_files(self):
        """NS 池应包含内置默认，且已并入 data/ 目录的 nameservers 文件"""
        pool = resolve_config['dns_pool']
        self.assertIn('223.5.5.5', pool)
        # data/nameservers.txt + nameservers_cn.txt 共 35 条，去重后应大于内置 5 条
        self.assertGreater(len(pool), 5)

    def test_pool_no_duplicates(self):
        """NS 池应去重"""
        pool = resolve_config['dns_pool']
        self.assertEqual(len(pool), len(set(pool)))

    def test_get_resolver_uses_pool_subset(self):
        """未指定 nameservers 时应使用池内随机子集（每线程最多 8 个）"""
        import threading
        from common import resolve as resolve_module
        resolve_module._resolver_local = threading.local()

        resolver = resolve_module._get_resolver()
        used = list(resolver.nameservers)
        self.assertTrue(1 <= len(used) <= 8)
        for ns in used:
            self.assertIn(ns, resolve_config['dns_pool'])

    def test_get_resolver_explicit_nameservers(self):
        """显式指定 nameservers 时应原样使用"""
        import threading
        from common import resolve as resolve_module
        resolve_module._resolver_local = threading.local()

        resolver = resolve_module._get_resolver(['10.0.0.1', '10.0.0.2'])
        self.assertEqual(list(resolver.nameservers), ['10.0.0.1', '10.0.0.2'])


if __name__ == '__main__':
    unittest.main()