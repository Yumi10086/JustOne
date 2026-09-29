"""
Unit tests for modules/certificates/crtsh.py
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.certificates.crtsh import Crtsh, run as crtsh_run


class TestCrtsh(unittest.TestCase):
    """测试 Crtsh 类"""

    def setUp(self):
        self.domain = 'example.com'

    def test_init_basic(self):
        """测试基本初始化"""
        module = Crtsh(self.domain)
        self.assertEqual(module.module, 'Crtsh')
        self.assertEqual(module.source, 'crts.sh')
        self.assertEqual(module.domain, self.domain)

    def test_init_with_config(self):
        """测试带配置初始化"""
        config = {'timeout': 60}
        module = Crtsh(self.domain, config)
        self.assertEqual(module.timeout, 60)

    def test_default_timeout(self):
        """测试默认超时"""
        module = Crtsh(self.domain)
        self.assertIsNotNone(module.timeout)

    def test_subdomains_initially_empty(self):
        """测试子域名初始为空"""
        module = Crtsh(self.domain)
        self.assertEqual(len(module.subdomains), 0)

    def test_start_time_set_on_init(self):
        """测试初始化时设置开始时间"""
        module = Crtsh(self.domain)
        self.assertIsNotNone(module.start)

    def test_finish_sets_end_time_and_elapse(self):
        """测试 finish 方法设置结束时间和耗时"""
        module = Crtsh(self.domain)
        module.begin()
        module.finish()
        self.assertIsNotNone(module.end)
        self.assertIsNotNone(module.elapse)

    def test_run_returns_set(self):
        """测试 run 方法返回集合"""
        module = Crtsh(self.domain)
        result = module.run()
        self.assertIsInstance(result, set)


class TestCrtshRun(unittest.TestCase):
    """测试 crtsh_run 函数"""

    def test_run_function_exists(self):
        """测试 run 函数存在"""
        self.assertIsNotNone(crtsh_run)
        self.assertTrue(callable(crtsh_run))

    def test_run_returns_set(self):
        """测试 run 函数返回集合"""
        result = crtsh_run('example.com')
        self.assertIsInstance(result, set)


if __name__ == '__main__':
    unittest.main()