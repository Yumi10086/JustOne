"""
Unit tests for modules/altdns.py
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.altdns import Altdns, altdns_config, set_altdns_config, run


class TestAltdnsConfig(unittest.TestCase):
    """测试置换模块配置函数"""

    def setUp(self):
        self._backup = altdns_config.copy()

    def tearDown(self):
        altdns_config.clear()
        altdns_config.update(self._backup)

    def test_default_config(self):
        """测试默认配置"""
        self.assertTrue(altdns_config['enabled'])
        self.assertEqual(altdns_config['concurrent'], 50)
        self.assertIsNone(altdns_config['wordlist'])
        self.assertTrue(altdns_config['prefix'])
        self.assertTrue(altdns_config['suffix'])
        self.assertTrue(altdns_config['number'])
        self.assertTrue(altdns_config['insert'])
        self.assertTrue(altdns_config['wildcard_check'])
        self.assertTrue(altdns_config['wildcard_deal'])
        self.assertEqual(altdns_config['wildcard_probes'], 3)
        self.assertFalse(altdns_config['wildcard_cidr'])

    def test_set_altdns_config(self):
        """测试设置配置"""
        set_altdns_config({'concurrent': 100, 'prefix': False})
        self.assertEqual(altdns_config['concurrent'], 100)
        self.assertFalse(altdns_config['prefix'])
        self.assertTrue(altdns_config['suffix'])


class TestAltdnsInit(unittest.TestCase):
    """测试 Altdns 类初始化"""

    def setUp(self):
        self._backup = altdns_config.copy()
        altdns_config.update({
            'enabled': True,
            'concurrent': 50,
            'wordlist': None,
            'prefix': True,
            'suffix': True,
            'number': True,
            'insert': True,
        })

    def tearDown(self):
        altdns_config.clear()
        altdns_config.update(self._backup)

    def test_init_with_defaults(self):
        """测试使用默认配置初始化"""
        module = Altdns('example.com', {'www.example.com'})
        self.assertEqual(module.domain, 'example.com')
        self.assertEqual(module.subdomains, {'www.example.com'})
        self.assertEqual(module.concurrent, 50)
        self.assertTrue(module.enable_prefix)
        self.assertTrue(module.enable_suffix)
        self.assertTrue(module.enable_number)
        self.assertTrue(module.enable_insert)
        self.assertIsNone(module.wordlist_path)
        self.assertEqual(module.new_subdomains, set())
        self.assertIsNone(module.elapse)
        self.assertTrue(module.wildcard_check)
        self.assertTrue(module.wildcard_deal)
        self.assertEqual(module.wildcard_probes, 3)
        self.assertFalse(module.wildcard_cidr)
        self.assertIsNone(module._wildcard_info)

    def test_init_with_custom_config(self):
        """测试使用自定义配置初始化"""
        config = {
            'concurrent': 20,
            'prefix': False,
            'suffix': True,
            'number': False,
            'insert': True,
            'wordlist': '/tmp/test.txt',
        }
        module = Altdns('example.com', {'www.example.com'}, config)
        self.assertEqual(module.concurrent, 20)
        self.assertFalse(module.enable_prefix)
        self.assertTrue(module.enable_suffix)
        self.assertFalse(module.enable_number)
        self.assertTrue(module.enable_insert)
        self.assertEqual(module.wordlist_path, '/tmp/test.txt')

    def test_init_with_none_config(self):
        """测试 config 为 None 时"""
        module = Altdns('example.com', {'www.example.com'}, None)
        self.assertEqual(module.concurrent, 50)
        self.assertTrue(module.enable_prefix)

    def test_init_empty_subdomains(self):
        """测试空子域名集合"""
        module = Altdns('example.com', set())
        self.assertEqual(module.subdomains, set())


class TestExtractLabel(unittest.TestCase):
    """测试 _extract_label 方法"""

    def setUp(self):
        self.module = Altdns('example.com', set())

    def test_extract_standard_subdomain(self):
        """测试标准子域名提取"""
        self.assertEqual(self.module._extract_label('www.example.com'), 'www')

    def test_extract_multi_level_subdomain(self):
        """测试多级子域名提取"""
        self.assertEqual(
            self.module._extract_label('deep.sub.example.com'), 'deep.sub'
        )

    def test_extract_no_suffix(self):
        """测试不匹配目标域名的子域名"""
        self.assertEqual(
            self.module._extract_label('other-domain.com'), 'other-domain.com'
        )

    def test_extract_exact_domain(self):
        """测试恰好是目标域名本身——源码返回原字符串而非空字符串"""
        self.assertEqual(
            self.module._extract_label('example.com'), 'example.com'
        )

    def test_extract_empty_string(self):
        """测试空字符串"""
        self.assertEqual(self.module._extract_label(''), '')


class TestLoadWordlist(unittest.TestCase):
    """测试 load_wordlist 方法"""

    def setUp(self):
        self.module = Altdns('example.com', set())

    @patch('modules.altdns.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='word1\nword2\n#comment\n\nword3\n')
    def test_load_wordlist_success(self, mock_file, mock_exists):
        """测试成功加载词表"""
        mock_exists.return_value = True
        self.module.wordlist_path = '/fake/wordlist.txt'
        result = self.module.load_wordlist()
        self.assertTrue(result)
        self.assertEqual(self.module.wordlist_lines, ['word1', 'word2', 'word3'])

    @patch('modules.altdns.Path.exists')
    def test_load_wordlist_file_not_exists(self, mock_exists):
        """测试词表文件不存在"""
        mock_exists.return_value = False
        self.module.wordlist_path = '/nonexistent/wordlist.txt'
        result = self.module.load_wordlist()
        self.assertFalse(result)

    @patch('modules.altdns.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='')
    def test_load_wordlist_empty_file(self, mock_file, mock_exists):
        """测试空词表文件"""
        mock_exists.return_value = True
        self.module.wordlist_path = '/fake/empty.txt'
        result = self.module.load_wordlist()
        self.assertTrue(result)
        self.assertEqual(self.module.wordlist_lines, [])

    @patch('modules.altdns.Path.exists')
    @patch('builtins.open', side_effect=PermissionError('Permission denied'))
    def test_load_wordlist_permission_error(self, mock_file, mock_exists):
        """测试读取权限错误"""
        mock_exists.return_value = True
        self.module.wordlist_path = '/fake/wordlist.txt'
        result = self.module.load_wordlist()
        self.assertFalse(result)

    @patch('modules.altdns.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='default1\ndefault2\n')
    def test_load_wordlist_default_path(self, mock_file, mock_exists):
        """测试使用默认路径加载词表——默认路径存在"""
        mock_exists.return_value = True
        self.module.wordlist_path = None
        result = self.module.load_wordlist()
        self.assertTrue(result)
        self.assertEqual(self.module.wordlist_lines, ['default1', 'default2'])

    @patch('modules.altdns.Path.exists')
    def test_load_wordlist_no_default_path(self, mock_exists):
        """测试默认路径也不存在"""
        mock_exists.return_value = False
        self.module.wordlist_path = None
        result = self.module.load_wordlist()
        self.assertFalse(result)


class TestGenerateCandidates(unittest.TestCase):
    """测试 generate_candidates 方法"""

    def setUp(self):
        self.module = Altdns('example.com', {'www.example.com'})
        self.module.wordlist_lines = ['test', 'dev', 'stg']

    def test_generate_with_prefix(self):
        """测试前缀置换"""
        self.module.enable_suffix = False
        self.module.enable_number = False
        self.module.enable_insert = False
        candidates = self.module.generate_candidates()
        expected = {
            'test-www.example.com',
            'dev-www.example.com',
            'stg-www.example.com',
        }
        self.assertEqual(candidates, expected)

    def test_generate_with_suffix(self):
        """测试后缀置换"""
        self.module.enable_prefix = False
        self.module.enable_number = False
        self.module.enable_insert = False
        candidates = self.module.generate_candidates()
        expected = {
            'www-test.example.com',
            'www-dev.example.com',
            'www-stg.example.com',
        }
        self.assertEqual(candidates, expected)

    def test_generate_with_number(self):
        """测试数字后缀置换"""
        self.module.enable_prefix = False
        self.module.enable_suffix = False
        self.module.enable_insert = False
        candidates = self.module.generate_candidates()
        self.assertEqual(len(candidates), 10)
        for i in range(1, 11):
            self.assertIn(f'www{i}.example.com', candidates)

    def test_generate_with_insert(self):
        """测试插入置换"""
        self.module = Altdns('example.com', {'apidev.example.com'})
        self.module.wordlist_lines = ['api', 'dev']
        self.module.enable_prefix = False
        self.module.enable_suffix = False
        self.module.enable_number = False
        candidates = self.module.generate_candidates()
        self.assertIn('api-dev.example.com', candidates)

    def test_generate_insert_no_duplicate_hyphen(self):
        """测试插入时避免重复连字符"""
        self.module = Altdns('example.com', {'a-b.example.com'})
        self.module.wordlist_lines = ['a']
        self.module.enable_prefix = False
        self.module.enable_suffix = False
        self.module.enable_number = False
        candidates = self.module.generate_candidates()
        self.assertNotIn('a--b.example.com', candidates)

    def test_generate_excludes_original(self):
        """测试候选中排除原始子域名"""
        self.module = Altdns('example.com', {'test.example.com'})
        self.module.wordlist_lines = ['test']
        self.module.enable_suffix = False
        self.module.enable_number = False
        self.module.enable_insert = False
        candidates = self.module.generate_candidates()
        self.assertNotIn('test.example.com', candidates)

    def test_generate_empty_wordlist(self):
        """测试空词表返回空集合"""
        self.module.wordlist_lines = []
        candidates = self.module.generate_candidates()
        self.assertEqual(candidates, set())

    def test_generate_empty_labels(self):
        """测试空标签子域名——example.com 提取后不为空，会生成候选"""
        self.module = Altdns('example.com', {'example.com'})
        self.module.wordlist_lines = ['test']
        self.module.enable_number = False
        self.module.enable_insert = False
        candidates = self.module.generate_candidates()
        # example.com 提取后是 'example.com'，不是空字符串
        self.assertIn('test-example.com.example.com', candidates)
        self.assertIn('example.com-test.example.com', candidates)

    def test_generate_all_rules_combined(self):
        """测试所有规则同时启用"""
        candidates = self.module.generate_candidates()
        self.assertIn('test-www.example.com', candidates)   # prefix
        self.assertIn('www-test.example.com', candidates)   # suffix
        self.assertIn('www1.example.com', candidates)       # number

    def test_generate_multi_level_subdomain(self):
        """测试多级子域名置换"""
        self.module = Altdns('example.com', {'api.v1.example.com'})
        self.module.wordlist_lines = ['test']
        self.module.enable_number = False
        self.module.enable_insert = False
        candidates = self.module.generate_candidates()
        self.assertIn('test-api.v1.example.com', candidates)
        self.assertIn('api.v1-test.example.com', candidates)


class TestResolveBatch(unittest.TestCase):
    """测试 resolve_batch 方法"""

    def setUp(self):
        self.module = Altdns('example.com', set())
        self.module.concurrent = 2

    @patch('modules.altdns.resolve.resolve_domain')
    def test_resolve_filters_wildcard(self, mock_resolve):
        """测试泛解析候选被过滤"""
        from common.wildcard import WildcardInfo
        self.module._wildcard_info = WildcardInfo(
            domain='example.com', detected=True, ips={'1.2.3.4'}
        )

        def side_effect(domain):
            if domain == 'wild.example.com':
                return {'ip': '1.2.3.4'}
            if domain == 'real.example.com':
                return {'ip': '9.9.9.9'}
            return None

        mock_resolve.side_effect = side_effect
        candidates = {'wild.example.com', 'real.example.com'}
        results = self.module.resolve_batch(candidates, show_progress=False)
        self.assertEqual(results, {'real.example.com'})

    @patch('modules.altdns.resolve.resolve_domain')
    def test_resolve_single_success(self, mock_resolve):
        """测试单个成功解析"""
        mock_resolve.return_value = {'ip': ['1.2.3.4']}
        candidates = {'www.example.com'}
        results = self.module.resolve_batch(candidates, show_progress=False)
        self.assertEqual(results, {'www.example.com'})

    @patch('modules.altdns.resolve.resolve_domain')
    def test_resolve_single_no_ip(self, mock_resolve):
        """测试解析成功但无 IP"""
        mock_resolve.return_value = {'ip': []}
        candidates = {'www.example.com'}
        results = self.module.resolve_batch(candidates, show_progress=False)
        self.assertEqual(results, set())

    @patch('modules.altdns.resolve.resolve_domain')
    def test_resolve_single_none_result(self, mock_resolve):
        """测试解析返回 None"""
        mock_resolve.return_value = None
        candidates = {'www.example.com'}
        results = self.module.resolve_batch(candidates, show_progress=False)
        self.assertEqual(results, set())

    @patch('modules.altdns.resolve.resolve_domain')
    def test_resolve_multiple_candidates(self, mock_resolve):
        """测试多个候选解析"""
        def side_effect(domain):
            return {'ip': ['1.2.3.4']} if domain == 'www.example.com' else None
        mock_resolve.side_effect = side_effect
        candidates = {'www.example.com', 'fake.example.com'}
        results = self.module.resolve_batch(candidates, show_progress=False)
        self.assertEqual(results, {'www.example.com'})
        self.assertEqual(mock_resolve.call_count, 2)

    @patch('modules.altdns.resolve.resolve_domain')
    def test_resolve_exception_handling(self, mock_resolve):
        """测试解析异常处理"""
        mock_resolve.side_effect = Exception('DNS Error')
        candidates = {'www.example.com'}
        results = self.module.resolve_batch(candidates, show_progress=False)
        self.assertEqual(results, set())

    def test_resolve_empty_candidates(self):
        """测试空候选集合"""
        results = self.module.resolve_batch(set(), show_progress=False)
        self.assertEqual(results, set())

    @patch('modules.altdns.resolve.resolve_domain')
    def test_resolve_single_thread_mode(self, mock_resolve):
        """测试单线程模式 (concurrent=1)"""
        self.module.concurrent = 1
        mock_resolve.return_value = {'ip': ['1.2.3.4']}
        candidates = {'a.example.com', 'b.example.com'}
        results = self.module.resolve_batch(candidates, show_progress=False)
        self.assertEqual(results, {'a.example.com', 'b.example.com'})


class TestRun(unittest.TestCase):
    """测试 run 方法（完整流程）"""

    def setUp(self):
        self.module = Altdns('example.com', {'www.example.com'})
        self.module.wildcard_check = False

    @patch.object(Altdns, 'load_wordlist')
    @patch.object(Altdns, 'generate_candidates')
    @patch.object(Altdns, 'resolve_batch')
    def test_run_full_flow(self, mock_resolve, mock_generate, mock_load):
        """测试完整运行流程"""
        mock_load.return_value = True
        mock_generate.return_value = {'test-www.example.com', 'dev-www.example.com'}
        mock_resolve.return_value = {'test-www.example.com'}
        result = self.module.run(show_progress=False)
        self.assertEqual(result, {'test-www.example.com'})
        self.assertEqual(self.module.new_subdomains, {'test-www.example.com'})
        self.assertIsNotNone(self.module.elapse)
        self.assertIsNotNone(self.module.end_time)

    def test_run_empty_subdomains(self):
        """测试无子域名时直接返回"""
        module = Altdns('example.com', set())
        result = module.run(show_progress=False)
        self.assertEqual(result, set())

    @patch.object(Altdns, 'load_wordlist')
    def test_run_load_wordlist_fail(self, mock_load):
        """测试词表加载失败"""
        mock_load.return_value = False
        result = self.module.run(show_progress=False)
        self.assertEqual(result, set())

    @patch.object(Altdns, 'load_wordlist')
    @patch.object(Altdns, 'generate_candidates')
    def test_run_no_candidates(self, mock_generate, mock_load):
        """测试无候选生成"""
        mock_load.return_value = True
        mock_generate.return_value = set()
        result = self.module.run(show_progress=False)
        self.assertEqual(result, set())


class TestGetElapse(unittest.TestCase):
    """测试 get_elapse 方法"""

    def test_get_elapse_before_run(self):
        """测试 run 前获取耗时"""
        module = Altdns('example.com', set())
        self.assertIsNone(module.get_elapse())

    @patch.object(Altdns, 'load_wordlist')
    @patch.object(Altdns, 'generate_candidates')
    @patch.object(Altdns, 'resolve_batch')
    def test_get_elapse_after_run(self, mock_resolve, mock_generate, mock_load):
        """测试 run 后获取耗时"""
        mock_load.return_value = True
        mock_generate.return_value = {'test.example.com'}
        mock_resolve.return_value = set()
        module = Altdns('example.com', {'www.example.com'})
        module.wildcard_check = False
        module.run(show_progress=False)
        self.assertIsInstance(module.get_elapse(), float)
        self.assertGreaterEqual(module.get_elapse(), 0)


class TestModuleEntry(unittest.TestCase):
    """测试模块入口函数 run"""

    @patch('modules.altdns.Altdns')  # 修正：源码中类名是 Altdns，但这里 patch 的是导入名
    def test_run_entry(self, mock_class):
        """测试模块入口调用"""
        mock_instance = MagicMock()
        mock_instance.run.return_value = {'found.example.com'}
        mock_class.return_value = mock_instance
        result = run('example.com', {'www.example.com'}, {'concurrent': 10})
        mock_class.assert_called_once_with('example.com', {'www.example.com'}, {'concurrent': 10})
        mock_instance.run.assert_called_once()
        self.assertEqual(result, {'found.example.com'})

    @patch('modules.altdns.Altdns')
    def test_run_entry_no_config(self, mock_class):
        """测试无配置参数的入口调用"""
        mock_instance = MagicMock()
        mock_instance.run.return_value = set()
        mock_class.return_value = mock_instance
        result = run('example.com', set())
        mock_class.assert_called_once_with('example.com', set(), None)
        self.assertEqual(result, set())
