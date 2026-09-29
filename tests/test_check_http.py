"""
Unit tests for modules/check/http.py
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.check.http import HTTPCheck


class TestHTTPCheck(unittest.TestCase):
    """测试 HTTPCheck 类"""

    def setUp(self):
        self.domain = 'example.com'

    def test_init_basic(self):
        """测试基本初始化"""
        checker = HTTPCheck(self.domain)
        self.assertEqual(checker.domain, self.domain)
        self.assertEqual(checker.module, 'HTTPCheck')
        self.assertEqual(checker.source, 'http_check')

    def test_init_with_config(self):
        """测试带配置初始化"""
        config = {'timeout': 10, 'verify_ssl': True}
        checker = HTTPCheck(self.domain, config)
        self.assertEqual(checker.timeout, 10)

    def test_check_invalid_subdomain(self):
        """测试无效子域名"""
        checker = HTTPCheck(self.domain)
        result = checker.check('invalid.nonexistent.domain123456789.com')
        self.assertIsNone(result)

    def test_check_valid_subdomain_timeout(self):
        """测试有效子域名超时场景（跳过，避免网络请求）"""
        self.skipTest('Skip to avoid network timeout')

    def test_run_empty_subdomains(self):
        """测试空子域名列表"""
        checker = HTTPCheck(self.domain)
        result = checker.run(set())
        self.assertEqual(len(result), 0)

    def test_run_none_subdomains(self):
        """测试未设置子域名"""
        checker = HTTPCheck(self.domain)
        result = checker.run()
        self.assertEqual(len(result), 0)

    def test_run_with_subdomains_invalid(self):
        """测试无效子域名列表（跳过，避免网络超时）"""
        self.skipTest('Skip to avoid network timeout')

    def test_infos_dict_initialized(self):
        """测试 infos 字典初始化"""
        checker = HTTPCheck(self.domain)
        self.assertIsInstance(checker.infos, dict)
        self.assertEqual(len(checker.infos), 0)


class TestHTTPCheckConfig(unittest.TestCase):
    """测试 HTTPCheck 配置"""

    def test_default_timeout(self):
        """测试默认超时时间"""
        from common.module import http_config
        checker = HTTPCheck('example.com')
        self.assertEqual(checker.timeout, http_config['timeout'])

    def test_custom_timeout(self):
        """测试自定义超时时间"""
        checker = HTTPCheck('example.com', {'timeout': 3})
        self.assertEqual(checker.timeout, 3)


if __name__ == '__main__':
    unittest.main()