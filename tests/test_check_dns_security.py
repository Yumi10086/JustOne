"""
Unit tests for modules/check/dns_security.py
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 直接导入被测模块（其依赖 common.module / config.logging 均为真实模块）。
# 注意：切勿在导入期覆盖 sys.modules['common'] 等全局模块——那会污染整个
# pytest 会话，导致后续其它测试 import common.* 报 "'common' is not a package"。
from modules.check.dns_security import DNSSecurityCheck, DNSSecurityResult, DOMESTIC_NS, INTERNATIONAL_NS, ALL_NS

# 导入 dns 异常用于模拟
import dns.resolver
import dns.exception


class TestDNSSecurityResult(unittest.TestCase):
    def test_dataclass_basic(self):
        r = DNSSecurityResult(check='测试', status='secure', detail='一切正常')
        self.assertEqual(r.check, '测试')
        self.assertEqual(r.status, 'secure')
        self.assertEqual(r.detail, '一切正常')

    def test_dataclass_with_extra(self):
        r = DNSSecurityResult(check='测试', status='suspicious', detail='差异', extra={'a': 1})
        self.assertEqual(r.extra, {'a': 1})


class TestDNSSecurityCheckInit(unittest.TestCase):
    def test_init_basic(self):
        check = DNSSecurityCheck('example.com')
        self.assertEqual(check.domain, 'example.com')
        self.assertEqual(check.module, 'DNSSecurityCheck')
        self.assertEqual(check.source, 'dns_security')
        self.assertEqual(len(check.results), 0)


class TestDNSSecurityCheck(unittest.TestCase):
    def setUp(self):
        self.check = DNSSecurityCheck('example.com')

    # ---------------------------------------------------------------------
    # 辅助方法：创建一个模拟的 resolver，根据 rdtype 返回预设答案
    # ---------------------------------------------------------------------
    def _make_mock_resolver(self, answers_dict):
        """
        answers_dict: dict，键为 rdtype (如 'DS', 'RRSIG')，值为列表（答案）或异常对象
        """
        mock_resolver = MagicMock()

        def resolve_side_effect(qname, rdtype, raise_on_no_answer=False):
            if rdtype in answers_dict:
                value = answers_dict[rdtype]
                if isinstance(value, Exception):
                    raise value
                # 模拟返回的答案对象可迭代
                answers = MagicMock()
                answers.__iter__ = MagicMock(return_value=iter(value))
                return answers
            else:
                raise dns.resolver.NoAnswer

        mock_resolver.resolve = MagicMock(side_effect=resolve_side_effect)
        return mock_resolver

    # ---------------------------------------------------------------------
    # 测试 check_dnssec
    # ---------------------------------------------------------------------
    def test_dnssec_secure(self):
        """同时存在 DS 和 RRSIG -> secure"""
        mock_res = self._make_mock_resolver({
            'DS': ['12345 13 2 ...'],
            'RRSIG': ['RRSIG ...'],
        })
        with patch.object(self.check, '_make_resolver', return_value=mock_res):
            result = self.check.check_dnssec()
            self.assertEqual(result.status, 'secure')
            self.assertIn('DNSSEC 配置完整', result.detail)
            self.assertEqual(result.extra['ds_count'], 1)
            self.assertEqual(result.extra['rrsig_count'], 1)

    def test_dnssec_insecure(self):
        """只有 DS，没有 RRSIG -> insecure"""
        mock_res = self._make_mock_resolver({
            'DS': ['12345 13 2 ...'],
            'RRSIG': dns.resolver.NoAnswer(),
        })
        with patch.object(self.check, '_make_resolver', return_value=mock_res):
            result = self.check.check_dnssec()
            self.assertEqual(result.status, 'insecure')
            self.assertIn('存在 DS 记录但无 RRSIG', result.detail)
            self.assertEqual(result.extra['ds_count'], 1)

    def test_dnssec_nsec(self):
        """没有 DS/RRSIG，但有 NSEC -> info 并注明 NSEC"""
        mock_res = self._make_mock_resolver({
            'NSEC': ['nsec.example.com. A RRSIG NSEC'],
        })
        with patch.object(self.check, '_make_resolver', return_value=mock_res):
            result = self.check.check_dnssec()
            self.assertEqual(result.status, 'info')
            self.assertIn('存在 NSEC 记录', result.detail)
            self.assertEqual(result.extra['nsec_count'], 1)

    def test_dnssec_not_enabled(self):
        """没有任何 DNSSEC 相关记录 -> info"""
        mock_res = self._make_mock_resolver({})
        with patch.object(self.check, '_make_resolver', return_value=mock_res):
            result = self.check.check_dnssec()
            self.assertEqual(result.status, 'info')
            self.assertEqual(result.detail, '未启用 DNSSEC')

    def test_dnssec_error(self):
        """解析过程抛出异常 -> error"""
        with patch.object(self.check, '_make_resolver', side_effect=Exception('Resolver failure')):
            result = self.check.check_dnssec()
            self.assertEqual(result.status, 'error')
            self.assertIn('DNSSEC 检测失败', result.detail)

    # ---------------------------------------------------------------------
    # 测试 check_consistency
    # ---------------------------------------------------------------------
    def test_consistency_identical(self):
        """国内国外返回相同 IP -> secure"""
        with patch.object(self.check, '_query') as mock_query:
            def side_effect(qname, rdtype, nameservers):
                if nameservers == DOMESTIC_NS or nameservers == INTERNATIONAL_NS:
                    return ['1.2.3.4', '5.6.7.8']
                return None
            mock_query.side_effect = side_effect
            result = self.check.check_consistency()
            self.assertEqual(result.status, 'secure')
            self.assertIn('解析结果一致', result.detail)
            self.assertEqual(result.extra['ip'], ['1.2.3.4', '5.6.7.8'])

    def test_consistency_different(self):
        """国内国外返回不同 IP -> suspicious"""
        with patch.object(self.check, '_query') as mock_query:
            def side_effect(qname, rdtype, nameservers):
                if nameservers == DOMESTIC_NS:
                    return ['1.2.3.4']
                elif nameservers == INTERNATIONAL_NS:
                    return ['5.6.7.8']
                return None
            mock_query.side_effect = side_effect
            result = self.check.check_consistency()
            self.assertEqual(result.status, 'suspicious')
            self.assertIn('解析结果差异', result.detail)
            self.assertIn('国内独有: 1.2.3.4', result.detail)
            self.assertIn('国外独有: 5.6.7.8', result.detail)

    def test_consistency_both_none(self):
        """国内国外均无法解析 -> error"""
        with patch.object(self.check, '_query', return_value=None):
            result = self.check.check_consistency()
            self.assertEqual(result.status, 'error')
            self.assertIn('国内与国外 DNS 均无法解析', result.detail)

    def test_consistency_one_none(self):
        """只有国内能解析，国外返回 None -> suspicious"""
        with patch.object(self.check, '_query') as mock_query:
            def side_effect(qname, rdtype, nameservers):
                if nameservers == DOMESTIC_NS:
                    return ['1.2.3.4']
                return None
            mock_query.side_effect = side_effect
            result = self.check.check_consistency()
            self.assertEqual(result.status, 'suspicious')
            self.assertIn('国内独有: 1.2.3.4', result.detail)

    def test_consistency_exception(self):
        """_query 抛出异常 -> error"""
        with patch.object(self.check, '_query', side_effect=Exception('Network error')):
            result = self.check.check_consistency()
            self.assertEqual(result.status, 'error')
            self.assertIn('一致性检测失败', result.detail)

    # ---------------------------------------------------------------------
    # 测试 check_hijack
    # ---------------------------------------------------------------------
    def test_hijack_secure(self):
        """NS 记录存在，且国内国外 A 查询均未返回 NXDOMAIN -> secure"""
        mock_res = MagicMock()
        ns_answers = MagicMock()
        ns_answers.__iter__ = MagicMock(return_value=iter(['ns1.example.com']))
        soa_answers = MagicMock()
        soa_answers.__iter__ = MagicMock(return_value=iter(['soa']))
        a_answers = MagicMock()
        a_answers.__iter__ = MagicMock(return_value=iter(['1.2.3.4']))

        def resolve_side_effect(qname, rdtype, raise_on_no_answer=False):
            if rdtype == 'NS':
                return ns_answers
            elif rdtype == 'SOA':
                return soa_answers
            else:
                return a_answers

        mock_res.resolve = MagicMock(side_effect=resolve_side_effect)

        with patch.object(self.check, '_make_resolver') as mock_make:
            mock_make.return_value = mock_res
            result = self.check.check_hijack()
            self.assertEqual(result.status, 'secure')
            self.assertIn('未检测到劫持迹象', result.detail)
            self.assertEqual(result.extra['ns_servers'], ['ns1.example.com'])
            self.assertEqual(result.extra['soa'], ['soa'])

    def test_hijack_nxdomain_detected(self):
        """国内解析器返回 NXDOMAIN，国外正常 -> suspicious"""
        resolver_ns_soa = MagicMock()
        resolver_ns_soa.resolve = MagicMock(
            side_effect=lambda qname, rdtype, **kw: MagicMock(__iter__=MagicMock(return_value=iter(['ns1']))) if rdtype == 'NS' else MagicMock(__iter__=MagicMock(return_value=iter(['soa'])))
        )

        resolver_domestic = MagicMock()
        resolver_domestic.resolve = MagicMock(side_effect=dns.resolver.NXDOMAIN)

        resolver_international = MagicMock()
        resolver_international.resolve = MagicMock(return_value=MagicMock(__iter__=MagicMock(return_value=iter(['9.9.9.9']))))

        with patch.object(self.check, '_make_resolver') as mock_make:
            mock_make.side_effect = [resolver_ns_soa, resolver_domestic, resolver_international]
            result = self.check.check_hijack()
            self.assertEqual(result.status, 'suspicious')
            self.assertIn('domestic 返回 NXDOMAIN', result.detail)

    def test_hijack_no_ns(self):
        """无法获取 NS 记录 -> info"""
        mock_res = MagicMock()
        mock_res.resolve = MagicMock(side_effect=dns.resolver.NoAnswer)
        with patch.object(self.check, '_make_resolver', return_value=mock_res):
            result = self.check.check_hijack()
            self.assertEqual(result.status, 'info')
            self.assertIn('无法获取 NS 记录', result.detail)

    def test_hijack_exception(self):
        """任何异常 -> error"""
        with patch.object(self.check, '_make_resolver', side_effect=Exception('Unexpected error')):
            result = self.check.check_hijack()
            self.assertEqual(result.status, 'error')
            self.assertIn('劫持检测异常', result.detail)

    # ---------------------------------------------------------------------
    # 测试 run()
    # ---------------------------------------------------------------------
    def test_run_calls_all_checks(self):
        """run() 应依次调用三个检测方法并返回结果列表"""
        with patch.object(self.check, 'check_dnssec') as mock_dns, \
             patch.object(self.check, 'check_consistency') as mock_cons, \
             patch.object(self.check, 'check_hijack') as mock_hij:
            mock_dns.return_value = DNSSecurityResult('DNSSEC', 'info', '')
            mock_cons.return_value = DNSSecurityResult('解析一致性', 'secure', '')
            mock_hij.return_value = DNSSecurityResult('劫持检测', 'secure', '')
            results = self.check.run()
            mock_dns.assert_called_once()
            mock_cons.assert_called_once()
            mock_hij.assert_called_once()
            self.assertEqual(len(results), 3)

    # ---------------------------------------------------------------------
    # 测试全局常量
    # ---------------------------------------------------------------------
    def test_nameservers_constants(self):
        self.assertIn('223.5.5.5', DOMESTIC_NS)
        self.assertIn('114.114.114.114', DOMESTIC_NS)
        self.assertIn('8.8.8.8', INTERNATIONAL_NS)
        self.assertIn('1.1.1.1', INTERNATIONAL_NS)
        self.assertEqual(ALL_NS, ['223.5.5.5', '114.114.114.114', '8.8.8.8', '1.1.1.1'])


if __name__ == '__main__':
    unittest.main()