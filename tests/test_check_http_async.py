"""
Unit tests for modules/check/http.py (AsyncHTTPCheck)
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.check.http import AsyncHTTPCheck, ALIVE_CODES


class TestAsyncHTTPCheck(unittest.TestCase):
    """测试 AsyncHTTPCheck 类"""

    def setUp(self):
        self.domain = 'example.com'

    def test_init_basic(self):
        """测试基本初始化"""
        checker = AsyncHTTPCheck(self.domain)
        self.assertEqual(checker.domain, self.domain)
        self.assertEqual(checker.concurrent, 100)

    def test_init_with_config(self):
        """测试带配置初始化"""
        config = {'timeout': 10}
        checker = AsyncHTTPCheck(self.domain, config, concurrent=50)
        self.assertEqual(checker.concurrent, 50)
        self.assertEqual(checker.timeout, 10)

    def test_init_default_values(self):
        """测试默认值"""
        checker = AsyncHTTPCheck(self.domain)
        self.assertEqual(checker.timeout, 5)
        self.assertEqual(checker.concurrent, 100)
        self.assertIsInstance(checker.results, list)
        self.assertEqual(len(checker.results), 0)

    def test_infos_dict_initialized(self):
        """测试 infos 字典初始化"""
        checker = AsyncHTTPCheck(self.domain)
        self.assertIsInstance(checker.infos, dict)
        self.assertEqual(len(checker.infos), 0)

    def test_run_empty_subdomains(self):
        """测试空子域名列表"""
        checker = AsyncHTTPCheck(self.domain)
        result = checker.run(set(), show_progress=False)
        self.assertEqual(len(result), 0)

    def test_run_none_subdomains(self):
        """测试 None 子域名"""
        checker = AsyncHTTPCheck(self.domain)
        result = checker.run(None, show_progress=False)
        self.assertEqual(len(result), 0)

    def test_run_invalid_subdomains(self):
        """测试无效子域名"""
        checker = AsyncHTTPCheck(self.domain)
        result = checker.run({'invalid.nonexistent.domain123456.com'}, show_progress=False)
        self.assertEqual(len(result), 0)

    def test_check_one_method_exists(self):
        """测试 check_one 方法存在"""
        checker = AsyncHTTPCheck(self.domain)
        self.assertTrue(hasattr(checker, 'check_one'))
        self.assertTrue(callable(getattr(checker, 'check_one')))

    def test_run_async_method_exists(self):
        """测试 run_async 方法存在"""
        checker = AsyncHTTPCheck(self.domain)
        self.assertTrue(hasattr(checker, 'run_async'))
        self.assertTrue(callable(getattr(checker, 'run_async')))


class TestAliveCodes(unittest.TestCase):
    """测试 ALIVE_CODES 常量"""

    def test_alive_codes_not_empty(self):
        """测试存活码集合不为空"""
        self.assertGreater(len(ALIVE_CODES), 0)

    def test_200_in_alive_codes(self):
        """测试 200 在存活码中"""
        self.assertIn(200, ALIVE_CODES)

    def test_404_in_alive_codes(self):
        """测试 404 在存活码中"""
        self.assertIn(404, ALIVE_CODES)

    def test_500_in_alive_codes(self):
        """测试 500 在存活码中"""
        self.assertIn(500, ALIVE_CODES)

    def test_302_in_alive_codes(self):
        """测试 302 在存活码中"""
        self.assertIn(302, ALIVE_CODES)

    def test_2xx_range(self):
        """测试 2xx 系列"""
        self.assertIn(201, ALIVE_CODES)
        self.assertIn(204, ALIVE_CODES)

    def test_3xx_range(self):
        """测试 3xx 系列"""
        self.assertIn(301, ALIVE_CODES)
        self.assertIn(307, ALIVE_CODES)

    def test_4xx_range(self):
        """测试 4xx 系列"""
        self.assertIn(401, ALIVE_CODES)
        self.assertIn(403, ALIVE_CODES)

    def test_5xx_range(self):
        """测试 5xx 系列"""
        self.assertIn(502, ALIVE_CODES)
        self.assertIn(503, ALIVE_CODES)


class TestAsyncHTTPCheckConcurrent(unittest.TestCase):
    """测试并发配置"""

    def setUp(self):
        self.domain = 'example.com'

    def test_custom_concurrent(self):
        """测试自定义并发数"""
        checker = AsyncHTTPCheck(self.domain, concurrent=200)
        self.assertEqual(checker.concurrent, 200)

    def test_low_concurrent(self):
        """测试低并发数"""
        checker = AsyncHTTPCheck(self.domain, concurrent=10)
        self.assertEqual(checker.concurrent, 10)


if __name__ == '__main__':
    unittest.main()