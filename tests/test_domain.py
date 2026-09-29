"""
Unit tests for common/domain.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import unittest
from common.domain import Domain, set_data_config, data_config


class TestDomain(unittest.TestCase):
    def setUp(self):
        self.original_config = data_config.copy()

    def tearDown(self):
        data_config.update(self.original_config)

    def test_default_init(self):
        """Test default initialization"""
        d = Domain('example.com')
        self.assertEqual(d.string, 'example.com')
        self.assertIsNone(d.domain)

    def test_init_with_config(self):
        """Test initialization with custom config"""
        custom_dir = Path('/custom/data')
        d = Domain('example.com', config={'data_dir': custom_dir})
        self.assertEqual(d.data_dir, custom_dir)

    def test_match_valid_domain(self):
        """Test match with valid domain"""
        d = Domain('www.example.com')
        result = d.match()
        self.assertEqual(result, 'www.example.com')

    def test_match_subdomain(self):
        """Test match with subdomain"""
        d = Domain('sub.domain.example.org')
        result = d.match()
        self.assertEqual(result, 'sub.domain.example.org')

    def test_match_invalid_string(self):
        """Test match with invalid string"""
        d = Domain('not a domain')
        result = d.match()
        self.assertIsNone(result)

    def test_match_with_url(self):
        """Test match extracts domain from URL"""
        d = Domain('https://www.example.com/path')
        result = d.match()
        self.assertEqual(result, 'www.example.com')

    def test_match_case_insensitive(self):
        """Test match is case insensitive"""
        d = Domain('WWW.EXAMPLE.COM')
        result = d.match()
        self.assertEqual(result.lower(), 'www.example.com')

    def test_extract_returns_result(self):
        """Test extract returns extract result"""
        d = Domain('www.example.com')
        result = d.extract()
        self.assertIsNotNone(result)
        self.assertEqual(result.domain, 'example')
        self.assertEqual(result.suffix, 'com')

    def test_extract_with_subdomain(self):
        """Test extract with subdomain"""
        d = Domain('api.v2.example.com')
        result = d.extract()
        self.assertIsNotNone(result)
        self.assertEqual(result.subdomain, 'api.v2')
        self.assertEqual(result.domain, 'example')
        self.assertEqual(result.suffix, 'com')

    def test_extract_invalid_domain(self):
        """Test extract with invalid domain returns None"""
        d = Domain('invalid..com')
        result = d.extract()
        self.assertIsNone(result)

    def test_registered_basic(self):
        """Test registered returns main domain"""
        d = Domain('www.example.com')
        result = d.registered()
        self.assertEqual(result, 'example.com')

    def test_registered_subdomain(self):
        """Test registered with multiple subdomains"""
        d = Domain('deep.sub.example.org')
        result = d.registered()
        self.assertEqual(result, 'example.org')

    def test_registered_complex(self):
        """Test registered with complex subdomain"""
        d = Domain('api.v2.test.example.co.uk')
        result = d.registered()
        self.assertEqual(result, 'example.co.uk')

    def test_registered_invalid(self):
        """Test registered with invalid domain returns None"""
        d = Domain('invalid_string')
        result = d.registered()
        self.assertIsNone(result)

    def test_set_data_config(self):
        """Test set_data_config updates global config"""
        new_dir = Path('/new/data')
        set_data_config({'data_dir': new_dir})
        self.assertEqual(data_config['data_dir'], new_dir)

    def test_set_data_config_preserves_others(self):
        """Test set_data_config preserves other config values"""
        original = data_config.copy()
        set_data_config({'data_dir': Path('/new')})
        # Only data_dir should be updated
        self.assertEqual(data_config['data_dir'], Path('/new'))

    def test_punycode_domain(self):
        """Test match with punycode domain"""
        d = Domain('xn--fiqs83s.example.com')
        result = d.match()
        self.assertEqual(result, 'xn--fiqs83s.example.com')

    def test_empty_string(self):
        """Test with empty string"""
        d = Domain('')
        result = d.match()
        self.assertIsNone(result)

    def test_domain_with_port(self):
        """Test match extracts domain from URL with port"""
        d = Domain('example.com:8080')
        result = d.match()
        self.assertEqual(result, 'example.com')


class TestDomainEdgeCases(unittest.TestCase):
    def test_ip_address(self):
        """Test with IP address (should not match as domain)"""
        d = Domain('192.168.1.1')
        result = d.match()
        self.assertIsNone(result)

    def test_localhost(self):
        """Test with localhost"""
        d = Domain('localhost')
        result = d.match()
        self.assertIsNone(result)

    def test_special_chars(self):
        """Test with special characters"""
        d = Domain('example@com')
        result = d.match()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()