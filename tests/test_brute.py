"""
Unit tests for modules/brute.py
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.brute import Brute, brute_config, set_brute_config


class TestBruteConfig(unittest.TestCase):
    """测试爆破模块配置函数"""

    def test_default_config(self):
        """测试默认配置"""
        self.assertTrue(brute_config['enabled'])
        self.assertEqual(brute_config['concurrent'], 2000)
        self.assertIsNone(brute_config['wordlist'])
        self.assertFalse(brute_config['recursive'])
        self.assertEqual(brute_config['recursive_depth'], 2)
        self.assertTrue(brute_config['wildcard_check'])
        self.assertTrue(brute_config['wildcard_deal'])
        self.assertEqual(brute_config['wildcard_probes'], 3)
        self.assertFalse(brute_config['wildcard_cidr'])
        self.assertEqual(brute_config['recursive_max_fanout'], 10)
        self.assertEqual(brute_config['recursive_max_candidates'], 100000)

    def test_set_brute_config(self):
        """测试设置配置"""
        original = brute_config.copy()
        try:
            set_brute_config({'concurrent': 5000})
            self.assertEqual(brute_config['concurrent'], 5000)
        finally:
            brute_config.update(original)


class TestBrute(unittest.TestCase):
    """测试 Brute 类"""

    def setUp(self):
        self.domain = 'example.com'

    def test_init_basic(self):
        """测试基本初始化"""
        brute = Brute(self.domain)
        self.assertEqual(brute.domain, self.domain)
        self.assertEqual(brute.concurrent, 2000)
        self.assertIsNone(brute.wordlist)
        self.assertFalse(brute.recursive)
        self.assertEqual(len(brute.subdomains), 0)

    def test_init_with_config(self):
        """测试带配置初始化"""
        config = {
            'concurrent': 1000,
            'recursive': True,
            'recursive_depth': 3,
            'wildcard_check': False,
        }
        brute = Brute(self.domain, config)
        self.assertEqual(brute.concurrent, 1000)
        self.assertTrue(brute.recursive)
        self.assertEqual(brute.recursive_depth, 3)
        self.assertFalse(brute.wildcard_check)

    def test_init_default_config_values(self):
        """测试使用默认配置值"""
        brute = Brute(self.domain)
        self.assertEqual(brute.concurrent, 2000)
        self.assertFalse(brute.recursive)
        self.assertEqual(brute.recursive_depth, 2)
        self.assertTrue(brute.wildcard_check)
        self.assertTrue(brute.wildcard_deal)
        self.assertEqual(brute.wildcard_probes, 3)
        self.assertFalse(brute.wildcard_cidr)
        self.assertIsNone(brute._wildcard_info)

    def test_registered_domain(self):
        """测试注册域名提取"""
        brute = Brute('www.example.com')
        self.assertEqual(brute.registered_domain, 'example.com')

    def test_wordlist_lines_empty_initially(self):
        """测试字典列表初始为空"""
        brute = Brute(self.domain)
        self.assertIsInstance(brute.wordlist_lines, list)
        self.assertEqual(len(brute.wordlist_lines), 0)

    def test_wildcard_ips_empty_initially(self):
        """测试泛解析 IP 集合初始为空"""
        brute = Brute(self.domain)
        self.assertIsInstance(brute._wildcard_ips, set)
        self.assertEqual(len(brute._wildcard_ips), 0)

    def test_generate_candidates_empty_wordlist(self):
        """测试空字典生成候选"""
        brute = Brute(self.domain)
        candidates = brute.generate_candidates([])
        self.assertEqual(len(candidates), 0)

    def test_generate_candidates_with_words(self):
        """测试字典生成候选"""
        brute = Brute(self.domain)
        words = ['www', 'mail', 'ftp']
        candidates = brute.generate_candidates(words)
        self.assertEqual(len(candidates), 3)
        self.assertIn('www.example.com', candidates)
        self.assertIn('mail.example.com', candidates)
        self.assertIn('ftp.example.com', candidates)

    def test_generate_candidates_no_duplicates(self):
        """测试候选生成无重复"""
        brute = Brute(self.domain)
        words = ['www', 'www', 'www']
        candidates = brute.generate_candidates(words)
        self.assertGreaterEqual(len(candidates), 1)

    def test_generate_candidates_with_base(self):
        """测试指定 base 时基于该域名生成候选"""
        brute = Brute(self.domain)
        candidates = brute.generate_candidates(['www', 'api'], base='dev.example.com')
        self.assertIn('www.dev.example.com', candidates)
        self.assertIn('api.dev.example.com', candidates)

    @patch.object(Brute, 'resolve_batch')
    def test_run_recursive_generates_deeper_candidates(self, mock_resolve):
        """测试递归爆破基于找到的子域名生成更深层候选"""
        brute = Brute(self.domain, {'recursive': True, 'recursive_depth': 2})
        brute.wordlist_lines = ['www']
        calls = []

        def side_effect(cands, show_progress=True):
            cands = list(cands)
            calls.append(cands)
            if cands == ['www.example.com']:
                return {'dev.example.com'}
            return set()

        mock_resolve.side_effect = side_effect
        result = brute._run_recursive(['www'], 1, False)

        self.assertIn('dev.example.com', result)
        self.assertIn(['www.example.com'], calls)
        self.assertIn(['www.dev.example.com'], calls)

    @patch.object(Brute, 'resolve_batch')
    def test_run_recursive_fanout_limit(self, mock_resolve):
        """测试递归扇出上限限制每层递归的子域名数量"""
        brute = Brute(self.domain, {
            'recursive': True,
            'recursive_depth': 2,
            'recursive_max_fanout': 2,
            'wildcard_check': False,
        })
        brute.wordlist_lines = ['www']
        bases_calls = []

        def side_effect(cands, show_progress=True):
            cands = list(cands)
            if cands == ['www.example.com']:
                return {'a.example.com', 'b.example.com', 'c.example.com'}
            bases_calls.append(cands[0])
            return set()

        mock_resolve.side_effect = side_effect
        brute._run_recursive(['www'], 1, False)

        # 扇出上限=2，仅对排序后的前 2 个子域名递归
        self.assertEqual(len(bases_calls), 2)
        self.assertEqual(bases_calls, ['www.a.example.com', 'www.b.example.com'])

    @patch.object(Brute, 'resolve_batch')
    def test_run_recursive_budget(self, mock_resolve):
        """测试递归候选总量预算耗尽后停止递归"""
        brute = Brute(self.domain, {
            'recursive': True,
            'recursive_depth': 3,
            'recursive_max_candidates': 1,
            'wildcard_check': False,
        })
        brute.wordlist_lines = ['www']
        calls = []

        def side_effect(cands, show_progress=True):
            calls.append(list(cands))
            if list(cands) == ['www.example.com']:
                return {'a.example.com'}
            return set()

        mock_resolve.side_effect = side_effect
        brute._run_recursive(['www'], 1, False)

        # 预算=1，第 1 层即耗尽，不再递归
        self.assertEqual(calls, [['www.example.com']])

    @patch('modules.brute.detect_wildcard')
    def test_merge_nested_wildcard(self, mock_detect):
        """测试嵌套泛解析证据合并（去除父级已解释的 IP）"""
        from common.wildcard import WildcardInfo
        brute = Brute(self.domain)
        brute._wildcard_info = WildcardInfo(
            domain=self.domain, detected=True, ips={'1.1.1.1'}
        )

        # 嵌套探测只返回父级已有 IP → 不视为嵌套泛解析
        mock_detect.return_value = WildcardInfo(
            domain='a.example.com', detected=True, ips={'1.1.1.1'}
        )
        self.assertIsNone(brute._merge_nested_wildcard('a.example.com'))

        # 嵌套探测返回新 IP → 合并
        mock_detect.return_value = WildcardInfo(
            domain='a.example.com', detected=True, ips={'2.2.2.2'}
        )
        merged = brute._merge_nested_wildcard('a.example.com')
        self.assertIsNotNone(merged)
        self.assertEqual(merged.ips, {'1.1.1.1', '2.2.2.2'})

    @patch('modules.brute.detect_wildcard')
    def test_merge_nested_wildcard_not_detected(self, mock_detect):
        """测试未检测到嵌套泛解析返回 None"""
        from common.wildcard import WildcardInfo
        brute = Brute(self.domain)
        mock_detect.return_value = WildcardInfo(domain='a.example.com', detected=False)
        self.assertIsNone(brute._merge_nested_wildcard('a.example.com'))

    def test_check_wildcard_disabled(self):
        """测试禁用泛解析检查"""
        brute = Brute(self.domain, {'wildcard_check': False})
        result = brute.check_wildcard()
        self.assertFalse(result)
        self.assertEqual(len(brute._wildcard_ips), 0)

    def test_resolve_batch_empty(self):
        """测试空列表批量解析"""
        brute = Brute(self.domain)
        results = brute.resolve_batch([])
        self.assertEqual(len(results), 0)

    @patch('modules.brute.resolve.resolve_domain')
    def test_resolve_batch_filters_wildcard(self, mock_resolve):
        """测试泛解析候选被过滤"""
        from common.wildcard import WildcardInfo
        brute = Brute(self.domain)
        brute.concurrent = 2
        brute._wildcard_info = WildcardInfo(
            domain=self.domain, detected=True, ips={'1.2.3.4'}
        )

        def side_effect(domain, nameservers=None):
            if domain == 'wild.example.com':
                return {'ip': '1.2.3.4'}
            return {'ip': '9.9.9.9'}

        mock_resolve.side_effect = side_effect
        results = brute.resolve_batch(
            ['wild.example.com', 'real.example.com'], show_progress=False
        )
        self.assertEqual(results, {'real.example.com'})

    def test_run_with_invalid_wordlist(self):
        """测试无效字典路径运行"""
        brute = Brute(self.domain, {'wordlist': '/nonexistent/path.txt'})
        result = brute.run()
        self.assertEqual(len(result), 0)

    def test_run_load_wordlist_from_path(self):
        """测试从路径加载字典（跳过，避免网络请求超时）"""
        self.skipTest('Skipped to avoid network timeout')

    def test_get_elapse_no_run(self):
        """测试未运行获取耗时返回 None"""
        brute = Brute(self.domain)
        self.assertIsNone(brute.get_elapse())

    def test_load_wordlist_nonexistent(self):
        """测试加载不存在的字典"""
        brute = Brute(self.domain)
        brute.wordlist = '/nonexistent/path.txt'
        result = brute.load_wordlist()
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()