"""
Unit tests for modules/collect.py
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.collect import Collect, collect_config, set_collect_config


import pytest

# 真实网络依赖（搜索引擎/证书日志/DNS 流量/CLI 端到端）：CI 默认跳过，
# 本地用 pytest -m network 单独运行，或 pytest 全量运行
pytestmark = pytest.mark.network
class TestCollectConfig(unittest.TestCase):
    """测试收集调度器配置函数"""

    def test_default_config(self):
        """测试默认配置"""
        self.assertTrue(collect_config['enabled'])
        self.assertEqual(collect_config['module_timeout'], 120)
        self.assertEqual(collect_config['max_concurrent'], 25)
        self.assertFalse(collect_config['save_module_result'])

    def test_set_collect_config(self):
        """测试设置配置"""
        original = collect_config.copy()
        try:
            set_collect_config({'module_timeout': 60})
            self.assertEqual(collect_config['module_timeout'], 60)
        finally:
            collect_config.update(original)


class TestCollect(unittest.TestCase):
    """测试 Collect 类"""

    def setUp(self):
        self.domain = 'example.com'

    def test_init_basic(self):
        """测试基本初始化"""
        collect = Collect(self.domain)
        self.assertEqual(collect.domain, self.domain)
        self.assertIsNotNone(collect.registered_domain)
        self.assertEqual(len(collect.subdomains), 0)
        self.assertEqual(len(collect.results), 0)

    def test_init_with_config(self):
        """测试带配置初始化"""
        config = {
            'module_timeout': 60,
            'max_concurrent': 100,
            'save_module_result': True,
        }
        collect = Collect(self.domain, config)
        self.assertEqual(collect.module_timeout, 60)
        self.assertEqual(collect.max_concurrent, 100)
        self.assertTrue(collect.save_module_result)

    def test_init_default_config_values(self):
        """测试使用默认配置值"""
        collect = Collect(self.domain)
        self.assertEqual(collect.module_timeout, 120)
        self.assertEqual(collect.max_concurrent, 25)
        self.assertFalse(collect.save_module_result)

    def test_registered_domain(self):
        """测试注册域名提取"""
        collect = Collect('www.example.com')
        self.assertEqual(collect.registered_domain, 'example.com')

    def test_wildcard_attrs(self):
        """测试泛解析相关属性初始化"""
        collect = Collect(self.domain)
        self.assertIsNone(collect._wildcard_info)
        self.assertEqual(collect.wildcard_probes, 3)
        self.assertFalse(collect.wildcard_cidr)

    def test_add_subdomains_empty(self):
        """测试添加空子域名集合"""
        collect = Collect(self.domain)
        collect.add_subdomains(set())
        self.assertEqual(len(collect.subdomains), 0)

    def test_add_subdomains_normal(self):
        """测试正常添加子域名"""
        collect = Collect(self.domain)
        subdomains = {'sub1.example.com', 'sub2.example.com'}
        collect.add_subdomains(subdomains, 'test_module')
        self.assertEqual(len(collect.subdomains), 2)
        self.assertIn('sub1.example.com', collect.subdomains)

    def test_add_subdomains_deduplication(self):
        """测试子域名去重"""
        collect = Collect(self.domain)
        subdomains1 = {'sub1.example.com'}
        subdomains2 = {'sub1.example.com', 'sub2.example.com'}
        collect.add_subdomains(subdomains1, 'module1')
        collect.add_subdomains(subdomains2, 'module2')
        self.assertEqual(len(collect.subdomains), 2)

    def test_add_subdomains_module_results(self):
        """测试模块结果记录"""
        collect = Collect(self.domain)
        subdomains = {'sub1.example.com'}
        collect.add_subdomains(subdomains, 'test_module')
        self.assertIn('test_module', collect.modules_results)
        self.assertEqual(collect.modules_results['test_module'], subdomains)

    def test_get_module_results(self):
        """测试获取模块结果"""
        collect = Collect(self.domain)
        module_results = collect.get_module_results()
        self.assertIsInstance(module_results, dict)
        self.assertEqual(len(module_results), 0)

    def test_run_returns_list(self):
        """测试运行返回列表"""
        collect = Collect(self.domain, {'enable_search': False, 'enable_certificate': False, 'enable_dataset': False, 'enable_intelligence': False})
        result = collect.run()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)
        self.assertIsNotNone(collect.elapse)

    def test_search_modules_list(self):
        """测试搜索引擎模块列表"""
        collect = Collect(self.domain)
        self.assertIsInstance(collect.search_modules, list)
        self.assertGreater(len(collect.search_modules), 0)

    def test_certificate_modules_list(self):
        """测试证书模块列表"""
        collect = Collect(self.domain)
        self.assertIsInstance(collect.certificate_modules, list)
        self.assertGreater(len(collect.certificate_modules), 0)

    def test_dataset_modules_list(self):
        """测试数据集模块列表"""
        collect = Collect(self.domain)
        self.assertIsInstance(collect.dataset_modules, list)
        self.assertGreater(len(collect.dataset_modules), 0)

    def test_modules_loaded_by_default(self):
        """测试默认加载模块"""
        collect = Collect(self.domain)
        self.assertGreater(len(collect.search_modules), 0)
        self.assertGreater(len(collect.certificate_modules), 0)

    def test_run_module_normal(self):
        """测试正常执行模块（异步接口）"""
        import asyncio
        collect = Collect(self.domain)
        from modules.search import BaiduSearch
        module = BaiduSearch(collect.registered_domain, collect.config)
        result = asyncio.run(collect._run_module_async(module))
        # 网络异常/超时时返回 None，正常返回 (子域名集合, 耗时)
        if result is not None:
            subdomains, elapse = result
            self.assertIsInstance(subdomains, set)
            self.assertIsInstance(elapse, float)

    def test_add_custom_module(self):
        """测试添加自定义模块"""
        collect = Collect(self.domain, {'enable_search': False})
        self.assertEqual(len(collect.search_modules), 0)
        from modules.search import BaiduSearch
        collect.add_module(BaiduSearch, 'search')
        self.assertEqual(len(collect.search_modules), 1)

    def test_get_summary(self):
        """测试获取摘要"""
        collect = Collect(self.domain)
        summary = collect.get_summary()
        self.assertIn('domain', summary)
        self.assertIn('registered_domain', summary)
        self.assertIn('total_subdomains', summary)
        self.assertIn('modules_count', summary)
        self.assertIn('elapse', summary)


if __name__ == '__main__':
    unittest.main()