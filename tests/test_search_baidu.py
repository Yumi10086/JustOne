"""
Unit tests for modules/search/baidu.py
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.search.baidu import BaiduSearch, run as baidu_run


class TestBaiduSearch(unittest.TestCase):
    """测试 BaiduSearch 类"""

    def setUp(self):
        self.domain = 'example.com'

    def test_init_basic(self):
        """测试基本初始化"""
        module = BaiduSearch(self.domain)
        self.assertEqual(module.module, 'BaiduSearch')
        self.assertEqual(module.source, 'baidu.com')
        self.assertEqual(module.domain, self.domain)

    def test_init_with_config(self):
        """测试带配置初始化"""
        config = {'timeout': 60}
        module = BaiduSearch(self.domain, config)
        self.assertEqual(module.timeout, 60)

    def test_default_timeout(self):
        """测试默认超时"""
        module = BaiduSearch(self.domain)
        self.assertIsNotNone(module.timeout)

    def test_subdomains_initially_empty(self):
        """测试子域名初始为空"""
        module = BaiduSearch(self.domain)
        self.assertEqual(len(module.subdomains), 0)

    def test_infos_initially_empty(self):
        """测试信息字典初始为空"""
        module = BaiduSearch(self.domain)
        self.assertEqual(len(module.infos), 0)

    def test_results_initially_empty(self):
        """测试结果列表初始为空"""
        module = BaiduSearch(self.domain)
        self.assertEqual(len(module.results), 0)

    def test_start_time_set_on_init(self):
        """测试初始化时设置开始时间"""
        module = BaiduSearch(self.domain)
        self.assertIsNotNone(module.start)

    def test_finish_sets_end_time_and_elapse(self):
        """测试 finish 方法设置结束时间和耗时"""
        module = BaiduSearch(self.domain)
        module.begin()
        module.finish()
        self.assertIsNotNone(module.end)
        self.assertIsNotNone(module.elapse)

    def test_run_returns_set(self):
        """测试 run 方法返回集合"""
        module = BaiduSearch(self.domain)
        result = module.run()
        self.assertIsInstance(result, set)


class TestBaiduRun(unittest.TestCase):
    """测试 baidu_run 函数"""

    def test_run_function_exists(self):
        """测试 run 函数存在"""
        self.assertIsNotNone(baidu_run)
        self.assertTrue(callable(baidu_run))

    def test_run_returns_set(self):
        """测试 run 函数返回集合"""
        result = baidu_run('example.com')
        self.assertIsInstance(result, set)


if __name__ == '__main__':
    unittest.main()