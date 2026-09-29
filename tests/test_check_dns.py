"""
Unit tests for modules/check/dns.py
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.check.dns import DNSCheck


class TestDNSCheck(unittest.TestCase):
    """测试 DNSCheck 类"""

    def setUp(self):
        self.domain = 'example.com'

    def test_init_basic(self):
        """测试基本初始化"""
        checker = DNSCheck(self.domain)
        self.assertEqual(checker.domain, self.domain)
        self.assertEqual(checker.module, 'DNSCheck')
        self.assertEqual(checker.source, 'dns_check')

    def test_init_with_config(self):
        """测试带配置初始化"""
        config = {'timeout': 10, 'verify_ssl': True}
        checker = DNSCheck(self.domain, config)
        self.assertEqual(checker.timeout, 10)

    def test_check_nonexistent_subdomain(self):
        """测试不存在子域名的 DNS 解析"""
        checker = DNSCheck(self.domain)
        result = checker.check('nonexistent123456789.example.com')
        self.assertIsNone(result)

    def test_check_known_invalid(self):
        """测试已知无效子域名"""
        checker = DNSCheck(self.domain)
        result = checker.check('invalid-domain-that-does-not-exist-123456789.com')
        self.assertIsNone(result)

    def test_check_valid_google(self):
        """测试有效域名解析（跳过，避免网络请求）"""
        self.skipTest('Skip to avoid network timeout')

    def test_run_empty_subdomains(self):
        """测试空子域名列表"""
        checker = DNSCheck(self.domain)
        result = checker.run(set())
        self.assertEqual(len(result), 0)

    def test_run_none_subdomains(self):
        """测试未设置子域名"""
        checker = DNSCheck(self.domain)
        result = checker.run()
        self.assertEqual(len(result), 0)

    def test_run_with_nonexistent_subdomains(self):
        """测试不存在子域名列表（跳过，避免网络超时）"""
        self.skipTest('Skip to avoid network timeout')

    def test_infos_dict_initialized(self):
        """测试 infos 字典初始化"""
        checker = DNSCheck(self.domain)
        self.assertIsInstance(checker.infos, dict)
        self.assertEqual(len(checker.infos), 0)

    def test_check_returns_dict_with_ip(self):
        """测试解析成功返回包含 IP 的字典（跳过，避免网络请求）"""
        self.skipTest('Skip to avoid network timeout')

    def test_check_exception_handling(self):
        """测试异常处理"""
        checker = DNSCheck(self.domain)
        result = checker.check('')
        self.assertIsNone(result)


class TestDNSCheckConfig(unittest.TestCase):
    """测试 DNSCheck 配置"""

    def test_default_timeout(self):
        """测试默认超时时间"""
        from common.module import http_config
        checker = DNSCheck('example.com')
        self.assertEqual(checker.timeout, http_config['timeout'])

    def test_custom_timeout(self):
        """测试自定义超时时间"""
        checker = DNSCheck('example.com', {'timeout': 3})
        self.assertEqual(checker.timeout, 3)


if __name__ == '__main__':
    unittest.main()