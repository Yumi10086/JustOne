"""
Unit tests for common/wildcard.py
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.wildcard import (
    DEFAULT_PROBES,
    WildcardInfo,
    _split_addr,
    detect_and_filter,
    detect_wildcard,
    filter_subdomains,
    is_wildcard_subdomain,
    parse_record,
)


class TestSplitAddr(unittest.TestCase):
    """测试 _split_addr 字段归一化"""

    def test_comma_string(self):
        """测试逗号分隔字符串"""
        self.assertEqual(_split_addr('1.1.1.1,2.2.2.2'), {'1.1.1.1', '2.2.2.2'})

    def test_single_string(self):
        """测试单个字符串"""
        self.assertEqual(_split_addr('1.1.1.1'), {'1.1.1.1'})

    def test_list(self):
        """测试列表输入"""
        self.assertEqual(_split_addr(['1.1.1.1', '2.2.2.2']), {'1.1.1.1', '2.2.2.2'})

    def test_none_and_empty(self):
        """测试 None 与空值"""
        self.assertEqual(_split_addr(None), set())
        self.assertEqual(_split_addr(''), set())
        self.assertEqual(_split_addr([]), set())

    def test_strips_whitespace(self):
        """测试去空白"""
        self.assertEqual(_split_addr(' 1.1.1.1 , 2.2.2.2 '), {'1.1.1.1', '2.2.2.2'})


class TestParseRecord(unittest.TestCase):
    """测试 parse_record 解析结果字典"""

    def test_none(self):
        """测试 None 输入"""
        self.assertEqual(parse_record(None), (set(), set(), set()))

    def test_comma_ip(self):
        """测试逗号拼接的 IP"""
        ipv4, ipv6, cnames = parse_record({'ip': '1.1.1.1,2.2.2.2'})
        self.assertEqual(ipv4, {'1.1.1.1', '2.2.2.2'})
        self.assertEqual(cnames, set())

    def test_list_ip(self):
        """测试列表形式的 IP（兼容测试 mock 形状）"""
        ipv4, _, _ = parse_record({'ip': ['1.1.1.1']})
        self.assertEqual(ipv4, {'1.1.1.1'})

    def test_cname_and_ipv6(self):
        """测试 CNAME 与 IPv6 字段"""
        ipv4, ipv6, cnames = parse_record({
            'ipv6': '::1',
            'cname': 'a.example.com,b.example.com',
        })
        self.assertEqual(ipv4, set())
        self.assertEqual(ipv6, {'::1'})
        self.assertEqual(cnames, {'a.example.com', 'b.example.com'})


class TestWildcardMatches(unittest.TestCase):
    """测试 WildcardInfo.matches / matches_record"""

    def test_not_detected_always_false(self):
        """测试未检测到泛解析时恒为 False"""
        info = WildcardInfo(domain='example.com', detected=False, ips={'1.1.1.1'})
        self.assertFalse(info.matches({'1.1.1.1'}, set(), set()))

    def test_exact_ip_match(self):
        """测试精确 IP 命中"""
        info = WildcardInfo(domain='example.com', detected=True, ips={'1.1.1.1'})
        self.assertTrue(info.matches({'1.1.1.1'}, set(), set()))

    def test_extra_ip_no_match(self):
        """测试候选含额外 IP 时不判定为泛解析"""
        info = WildcardInfo(domain='example.com', detected=True, ips={'1.1.1.1'})
        self.assertFalse(info.matches({'1.1.1.1', '9.9.9.9'}, set(), set()))

    def test_cname_intersection(self):
        """测试 CNAME 命中"""
        info = WildcardInfo(domain='example.com', detected=True, cnames={'wild.example.net'})
        self.assertTrue(info.matches(set(), set(), {'wild.example.net'}))

    def test_cidr_enabled(self):
        """测试启用同 /24 网段匹配"""
        info = WildcardInfo(domain='example.com', detected=True, ips={'1.1.1.1'})
        self.assertTrue(info.matches({'1.1.1.99'}, set(), set(), include_cidr=True))

    def test_cidr_disabled(self):
        """测试未启用网段匹配时不同 IP 不命中"""
        info = WildcardInfo(domain='example.com', detected=True, ips={'1.1.1.1'})
        self.assertFalse(info.matches({'1.1.1.99'}, set(), set(), include_cidr=False))

    def test_ipv6_subset(self):
        """测试 IPv6 子集匹配"""
        info = WildcardInfo(domain='example.com', detected=True, ipv6s={'2001:db8::1'})
        self.assertTrue(info.matches(set(), {'2001:db8::1'}, set()))

    def test_matches_record(self):
        """测试 matches_record 便捷方法"""
        info = WildcardInfo(domain='example.com', detected=True, ips={'1.1.1.1'})
        self.assertTrue(info.matches_record({'ip': '1.1.1.1'}))
        self.assertFalse(info.matches_record({'ip': '2.2.2.2'}))

    def test_empty_candidate(self):
        """测试空解析结果不命中"""
        info = WildcardInfo(domain='example.com', detected=True, ips={'1.1.1.1'})
        self.assertFalse(info.matches(set(), set(), set()))


class TestDetectWildcard(unittest.TestCase):
    """测试 detect_wildcard"""

    @patch('common.wildcard._resolve_record')
    def test_detected(self, mock_resolve):
        """测试探测到泛解析"""
        mock_resolve.return_value = ({'1.1.1.1'}, set(), set())
        info = detect_wildcard('example.com', probes=2)
        self.assertTrue(info.detected)
        self.assertEqual(info.ips, {'1.1.1.1'})
        self.assertEqual(len(info.probes), 2)
        self.assertEqual(mock_resolve.call_count, 2)

    @patch('common.wildcard._resolve_record')
    def test_not_detected(self, mock_resolve):
        """测试未探测到泛解析"""
        mock_resolve.return_value = (set(), set(), set())
        info = detect_wildcard('example.com', probes=2)
        self.assertFalse(info.detected)
        self.assertEqual(info.ips, set())
        self.assertEqual(info.probes, [])

    @patch('common.wildcard._resolve_record')
    def test_default_probes(self, mock_resolve):
        """测试默认探测次数"""
        mock_resolve.return_value = (set(), set(), set())
        detect_wildcard('example.com')
        self.assertEqual(mock_resolve.call_count, DEFAULT_PROBES)


class TestIsWildcardSubdomain(unittest.TestCase):
    """测试 is_wildcard_subdomain"""

    @patch('common.wildcard._resolve_record')
    def test_wildcard_hit(self, mock_resolve):
        """测试命中泛解析"""
        mock_resolve.return_value = ({'1.1.1.1'}, set(), set())
        info = WildcardInfo(domain='example.com', detected=True, ips={'1.1.1.1'})
        self.assertTrue(is_wildcard_subdomain('a.example.com', info))

    def test_not_detected_short_circuit(self):
        """测试未检测到泛解析时短路，不发起解析"""
        info = WildcardInfo(domain='example.com', detected=False)
        with patch('common.wildcard._resolve_record') as mock_resolve:
            self.assertFalse(is_wildcard_subdomain('a.example.com', info))
            mock_resolve.assert_not_called()


class TestFilterSubdomains(unittest.TestCase):
    """测试 filter_subdomains"""

    @patch('common.wildcard._resolve_record')
    def test_separates_wildcard(self, mock_resolve):
        """测试正确分离泛解析与真实子域名"""
        info = WildcardInfo(domain='example.com', detected=True, ips={'1.2.3.4'})

        def side_effect(domain, nameservers=None):
            if domain == 'wild.example.com':
                return ({'1.2.3.4'}, set(), set())
            if domain == 'real.example.com':
                return ({'9.9.9.9'}, set(), set())
            return (set(), set(), set())

        mock_resolve.side_effect = side_effect
        kept, removed = filter_subdomains(
            ['wild.example.com', 'real.example.com'], info, concurrent=2
        )
        self.assertEqual(removed, {'wild.example.com'})
        self.assertEqual(kept, {'real.example.com'})

    def test_not_detected_keeps_all(self):
        """测试未检测到泛解析时原样保留，不发起解析"""
        info = WildcardInfo(domain='example.com', detected=False)
        with patch('common.wildcard._resolve_record') as mock_resolve:
            kept, removed = filter_subdomains(['a.example.com'], info)
            self.assertEqual(kept, {'a.example.com'})
            self.assertEqual(removed, set())
            mock_resolve.assert_not_called()

    def test_empty_input(self):
        """测试空输入"""
        info = WildcardInfo(domain='example.com', detected=True, ips={'1.2.3.4'})
        kept, removed = filter_subdomains([], info)
        self.assertEqual(kept, set())
        self.assertEqual(removed, set())


class TestRotationAndMerge(unittest.TestCase):
    """测试轮换 IP 自动网段匹配与结果合并"""

    @patch('common.wildcard._resolve_record')
    def test_rotation_auto_networks(self, mock_resolve):
        """测试探测到多个不同 IP 时自动推导 /24 网段"""
        mock_resolve.side_effect = [
            ({'1.2.3.4'}, set(), set()),
            ({'1.2.3.9'}, set(), set()),
        ]
        info = detect_wildcard('example.com', probes=2)
        self.assertTrue(info.detected)
        self.assertEqual(info.ips, {'1.2.3.4', '1.2.3.9'})
        self.assertIn('1.2.3.4/24', info.networks)
        # 同网段不同 IP，无需 include_cidr 也应命中
        self.assertTrue(info.matches({'1.2.3.200'}, set(), set()))

    @patch('common.wildcard._resolve_record')
    def test_stable_ip_no_networks(self, mock_resolve):
        """测试稳定单 IP 泛解析不推导网段（避免过度排除）"""
        mock_resolve.return_value = ({'1.2.3.4'}, set(), set())
        info = detect_wildcard('example.com', probes=2)
        self.assertEqual(info.networks, set())
        # 同 /24 的其它 IP 不应命中
        self.assertFalse(info.matches({'1.2.3.99'}, set(), set()))

    def test_merge(self):
        """测试合并两个泛解析结果取并集"""
        a = WildcardInfo(domain='example.com', detected=True, ips={'1.1.1.1'})
        b = WildcardInfo(domain='dev.example.com', detected=True, cnames={'x.net'})
        merged = a.merge(b)
        self.assertTrue(merged.detected)
        self.assertEqual(merged.ips, {'1.1.1.1'})
        self.assertEqual(merged.cnames, {'x.net'})

    def test_merge_none(self):
        """测试合并 None 返回自身"""
        a = WildcardInfo(domain='example.com', detected=True)
        self.assertIs(a.merge(None), a)


class TestDetectAndFilter(unittest.TestCase):
    """测试 detect_and_filter 组合函数"""

    @patch('common.wildcard._resolve_record')
    def test_detected_and_excludes(self, mock_resolve):
        """测试检测到泛解析并排除泛解析子域名"""
        def side_effect(name, nameservers=None):
            if name.startswith('_wc'):
                return ({'1.2.3.4'}, set(), set())
            if name == 'wild.example.com':
                return ({'1.2.3.4'}, set(), set())
            if name == 'real.example.com':
                return ({'9.9.9.9'}, set(), set())
            return (set(), set(), set())

        mock_resolve.side_effect = side_effect
        kept, removed, info = detect_and_filter(
            {'wild.example.com', 'real.example.com'},
            'example.com',
            probes=2,
            concurrent=2,
        )
        self.assertTrue(info.detected)
        self.assertEqual(removed, {'wild.example.com'})
        self.assertEqual(kept, {'real.example.com'})

    @patch('common.wildcard._resolve_record')
    def test_not_detected_keeps_all(self, mock_resolve):
        """测试未检测到泛解析时原样保留"""
        mock_resolve.return_value = (set(), set(), set())
        kept, removed, info = detect_and_filter(
            {'a.example.com'}, 'example.com', probes=2
        )
        self.assertFalse(info.detected)
        self.assertEqual(kept, {'a.example.com'})
        self.assertEqual(removed, set())


if __name__ == '__main__':
    unittest.main()
