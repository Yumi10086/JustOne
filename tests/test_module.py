"""
Unit tests for common/module.py
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
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from common.module import Module, http_config, set_http_config


class TestModule(unittest.TestCase):
    def setUp(self):
        self.original_config = http_config.copy()

    def tearDown(self):
        http_config.update(self.original_config)

    def test_default_init(self):
        """Test default initialization"""
        m = Module()
        self.assertEqual(m.module, 'Module')
        self.assertEqual(m.source, 'BaseModule')
        self.assertEqual(m.domain, '')
        self.assertEqual(m.timeout, 27)
        self.assertEqual(m.verify, False)
        self.assertEqual(m.subdomains, set())
        self.assertEqual(m.infos, {})
        self.assertEqual(m.results, [])

    def test_init_with_domain(self):
        """Test initialization with domain"""
        m = Module('example.com')
        self.assertEqual(m.domain, 'example.com')

    def test_init_with_config(self):
        """Test initialization with custom config"""
        config = {
            'timeout': 30,
            'verify_ssl': True,
            'proxy_enable': True,
            'save_module_result': True
        }
        m = Module('example.com', config)
        self.assertEqual(m.timeout, 30)
        self.assertEqual(m.verify, True)
        self.assertEqual(m.proxy_enable, True)
        self.assertEqual(m.save_module_result, True)

    def test_init_config_overrides_http_config(self):
        """Test that instance config overrides http_config"""
        set_http_config({'timeout': 15, 'verify_ssl': True})
        m = Module('example.com', config={'timeout': 20})
        self.assertEqual(m.timeout, 20)
        self.assertEqual(m.verify, True)

    def test_have_api_all_present(self):
        """Test have_api returns True when all APIs present"""
        m = Module()
        self.assertTrue(m.have_api('api_key', 'secret', 'token'))

    def test_have_api_some_missing(self):
        """Test have_api returns False when some APIs missing"""
        m = Module()
        self.assertFalse(m.have_api('api_key', None, 'token'))

    def test_have_api_all_missing(self):
        """Test have_api returns False when all APIs missing"""
        m = Module()
        self.assertFalse(m.have_api(None, None, None))

    def test_begin_logs(self):
        """Test begin method logs message"""
        m = Module('example.com')
        with patch('common.module.logger') as mock_logger:
            m.begin()
            mock_logger.debug.assert_called()

    def test_finish_calculates_elapse(self):
        """Test finish method calculates elapsed time"""
        m = Module('example.com')
        m.begin()
        import time
        time.sleep(0.01)
        with patch('common.module.logger') as mock_logger:
            m.finish()
            self.assertIsNotNone(m.elapse)
            self.assertIsNotNone(m.end)

    def test_match_subdomains_empty(self):
        """Test match_subdomains with empty response"""
        m = Module('example.com')
        result = m.match_subdomains(None)
        self.assertEqual(result, set())

    def test_match_subdomains_string(self):
        """Test match_subdomains with string response"""
        m = Module('example.com')
        html = 'sub.example.com test.example.com'
        with patch('common.utils.match_subdomains') as mock_match:
            mock_match.return_value = {'sub.example.com', 'test.example.com'}
            result = m.match_subdomains(html)
            self.assertEqual(result, {'sub.example.com', 'test.example.com'})

    def test_match_subdomains_response_object(self):
        """Test match_subdomains with response object"""
        m = Module('example.com')
        mock_resp = MagicMock()
        mock_resp.text = 'sub.example.com'

        with patch('common.utils.match_subdomains') as mock_match:
            mock_match.return_value = {'sub.example.com'}
            result = m.match_subdomains(mock_resp)
            self.assertEqual(result, {'sub.example.com'})

    def test_collect_subdomains(self):
        """Test collect_subdomains updates subdomains set"""
        m = Module('example.com')
        m.collect_subdomains('sub1.example.com sub2.example.com')
        self.assertEqual(len(m.subdomains), 2)

    def test_collect_subdomains_accumulates(self):
        """Test collect_subdomains accumulates results"""
        m = Module('example.com')
        m.collect_subdomains('sub1.example.com')
        m.collect_subdomains('sub2.example.com')
        self.assertEqual(len(m.subdomains), 2)

    def test_gen_result_empty(self):
        """Test gen_result generates empty result when no subdomains"""
        m = Module('example.com')
        m.gen_result()
        self.assertEqual(len(m.results), 1)
        result = m.results[0]
        self.assertIsNone(result['subdomain'])
        self.assertEqual(result['module'], 'Module')
        self.assertEqual(result['source'], 'BaseModule')

    def test_gen_result_with_subdomains(self):
        """Test gen_result generates results for each subdomain"""
        m = Module('example.com')
        m.subdomains = {'sub1.example.com', 'sub2.example.com'}
        m.gen_result()
        self.assertEqual(len(m.results), 2)
        for result in m.results:
            self.assertIn('subdomain', result)
            self.assertIn('http://', result['url'])
            self.assertEqual(result['module'], 'Module')
            self.assertEqual(result['source'], 'BaseModule')

    def test_gen_result_level_calculation(self):
        """Test gen_result calculates subdomain level correctly"""
        m = Module('example.com')
        m.subdomains = {'sub.example.com', 'deep.sub.example.com'}
        m.gen_result()
        results_by_subdomain = {r['subdomain']: r for r in m.results}
        self.assertEqual(results_by_subdomain['sub.example.com']['level'], 1)
        self.assertEqual(results_by_subdomain['deep.sub.example.com']['level'], 2)

    def test_gen_result_with_info(self):
        """Test gen_result uses info dict for additional fields"""
        m = Module('example.com')
        m.subdomains = {'sub.example.com'}
        m.infos = {'sub.example.com': {'ip': '1.2.3.4', 'cdn': 1}}
        m.gen_result()
        result = m.results[0]
        self.assertEqual(result['ip'], '1.2.3.4')
        self.assertEqual(result['cdn'], 1)

    def test_gen_result_list_cname(self):
        """Test gen_result handles list type cname/ip"""
        m = Module('example.com')
        m.subdomains = {'sub.example.com'}
        m.infos = {
            'sub.example.com': {
                'cname': ['cname1.com', 'cname2.com'],
                'ip': ['1.1.1.1', '2.2.2.2'],
                'ip_times': [100, 200],
                'cname_times': [50, 100],
                'ttl': [300, 600]
            }
        }
        m.gen_result()
        result = m.results[0]
        self.assertEqual(result['cname'], 'cname1.com,cname2.com')
        self.assertEqual(result['ip'], '1.1.1.1,2.2.2.2')
        self.assertEqual(result['ip_times'], '100,200')
        self.assertEqual(result['cname_times'], '50,100')
        self.assertEqual(result['ttl'], '300,600')

    def test_save_json_disabled(self):
        """Test save_json returns False when disabled"""
        m = Module('example.com')
        m.save_module_result = False
        result = m.save_json()
        self.assertFalse(result)

    def test_save_json_enabled(self):
        """Test save_json saves to file when enabled"""
        with tempfile.TemporaryDirectory() as tmpdir:
            m = Module('example.com', config={
                'save_module_result': True,
                'results_dir': Path(tmpdir)
            })
            m.subdomains = {'sub.example.com'}
            m.module = 'TestModule'
            m.source = 'test_source'
            m.elapse = 1.5
            m.infos = {}

            result = m.save_json()
            self.assertTrue(result)

            json_path = Path(tmpdir) / 'example.com' / 'TestModule' / 'test_source.json'
            self.assertTrue(json_path.exists())

            with open(json_path) as f:
                data = json.load(f)
                self.assertEqual(data['domain'], 'example.com')
                self.assertEqual(data['name'], 'TestModule')
                self.assertEqual(data['source'], 'test_source')
                self.assertEqual(data['find'], 1)
                self.assertIn('sub.example.com', data['subdomains'])

    def test_set_http_config(self):
        """Test set_http_config updates global config"""
        set_http_config({'timeout': 60, 'verify_ssl': True})
        self.assertEqual(http_config['timeout'], 60)
        self.assertEqual(http_config['verify_ssl'], True)

    def test_set_http_config_preserves_others(self):
        """Test set_http_config preserves other config values"""
        original = http_config.copy()
        set_http_config({'timeout': 60})
        self.assertEqual(http_config['verify_ssl'], original['verify_ssl'])
        self.assertEqual(http_config['proxy_enable'], original['proxy_enable'])

    def test_get_proxy_disabled(self):
        """Test get_proxy returns None when proxy disabled"""
        m = Module('example.com', config={'proxy_enable': False})
        result = m.get_proxy('TestModule')
        self.assertIsNone(result)

    def test_get_proxy_enabled(self):
        """Test get_proxy returns proxy when proxy_enable is True"""
        with patch('common.utils.get_random_proxy') as mock_proxy:
            mock_proxy.return_value = {'http': 'http://proxy:8080'}
            m = Module('example.com', config={'proxy_enable': True})
            self.assertIsNotNone(m.proxy)
            self.assertEqual(m.proxy['http'], 'http://proxy:8080')
            result = m.get_proxy('TestModule')
            self.assertEqual(result, m.proxy)


class TestModuleHTTPMethods(unittest.TestCase):
    def test_head_request(self):
        """Test head method makes request"""
        m = Module('example.com', config={'timeout': 5})
        m.header = {'User-Agent': 'TestAgent'}

        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.head.return_value = mock_response
            mock_session_class.return_value = mock_session

            with patch('common.utils.check_response', return_value=True):
                result = m.head('http://example.com')
                mock_session.head.assert_called_once()

    def test_get_request(self):
        """Test get method makes request"""
        m = Module('example.com', config={'timeout': 5})

        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session

            with patch('common.utils.check_response', return_value=True):
                result = m.get('http://example.com')
                mock_session.get.assert_called_once()

    def test_get_ignore_error(self):
        """Test get with ignore=True doesn't raise"""
        m = Module('example.com', config={'timeout': 5})

        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session.get.side_effect = Exception('Timeout')
            mock_session_class.return_value = mock_session

            result = m.get('http://example.com', ignore=True)
            self.assertIsNone(result)

    def test_post_request(self):
        """Test post method makes request"""
        m = Module('example.com', config={'timeout': 5})

        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.post.return_value = mock_response
            mock_session_class.return_value = mock_session

            with patch('common.utils.check_response', return_value=True):
                result = m.post('http://example.com', data={'key': 'value'})
                mock_session.post.assert_called_once()

    def test_delete_request(self):
        """Test delete method makes request"""
        m = Module('example.com', config={'timeout': 5})

        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.delete.return_value = mock_response
            mock_session_class.return_value = mock_session

            with patch('common.utils.check_response', return_value=True):
                result = m.delete('http://example.com')
                mock_session.delete.assert_called_once()

    def test_http_methods_check_response(self):
        """Test HTTP methods check response by default"""
        m = Module('example.com', config={'timeout': 5})

        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session

            with patch('common.utils.check_response', return_value=False):
                result = m.get('http://example.com')
                self.assertIsNone(result)

    def test_http_methods_no_check(self):
        """Test HTTP methods return raw response when check=False"""
        m = Module('example.com', config={'timeout': 5})

        with patch('requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session

            result = m.get('http://example.com', check=False)
            self.assertEqual(result, mock_response)


if __name__ == '__main__':
    unittest.main()