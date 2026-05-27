# -*- coding: utf-8 -*-
"""
子域名接管检测模块测试
"""

import json
from pathlib import Path
import unittest

import dns.resolver

from modules.takeover.fingerprints import load_fingerprints, match_cname, find_matching_fingerprint


class TestFingerprints(unittest.TestCase):
    """指纹模块测试"""

    def setUp(self):
        self.fingerprints = load_fingerprints()

    def test_load_fingerprints_returns_dict(self):
        self.assertIsInstance(self.fingerprints, dict)

    def test_load_fingerprints_not_empty(self):
        self.assertGreater(len(self.fingerprints), 0)

    def test_load_fingerprints_all_have_required_fields(self):
        required_fields = {'name', 'severity', 'cname', 'cname_match', 'http_check'}
        for service_id, fp in self.fingerprints.items():
            for field in required_fields:
                self.assertIn(field, fp, f'{service_id} 缺少字段 {field}')

    def test_cname_match_suffix_positive(self):
        fp = self.fingerprints.get('github-pages')
        self.assertIsNotNone(fp)
        result = match_cname('myblog.github.io', fp)
        self.assertEqual(result, '.github.io')

    def test_cname_match_suffix_negative(self):
        fp = self.fingerprints.get('github-pages')
        result = match_cname('myblog.s3.amazonaws.com', fp)
        self.assertIsNone(result)

    def test_cname_match_regex_positive(self):
        fp = self.fingerprints.get('aws-s3')
        result = match_cname('bucket.s3.amazonaws.com', fp)
        self.assertIsNotNone(result)

    def test_cname_match_contains_positive(self):
        test_fp = {
            'cname_match': 'contains',
            'cname': ['heroku'],
        }
        result = match_cname('app.herokuapp.com', test_fp)
        self.assertEqual(result, 'heroku')

    def test_find_matching_fingerprint_hit(self):
        result = find_matching_fingerprint('myblog.github.io', self.fingerprints)
        self.assertIsNotNone(result)
        service_id, fp, matched = result
        self.assertEqual(service_id, 'github-pages')

    def test_find_matching_fingerprint_miss(self):
        result = find_matching_fingerprint('normal.example.com', self.fingerprints)
        self.assertIsNone(result)

    def test_custom_path_loading(self):
        path = Path('data/takeover_fingerprints.json')
        fps = load_fingerprints(path)
        self.assertGreater(len(fps), 0)

    def test_match_cname_with_inline_dict(self):
        fp = {'cname_match': 'suffix', 'cname': ['.example.com']}
        result = match_cname('test.example.com', fp)
        self.assertEqual(result, '.example.com')

    def test_match_cname_empty_cname(self):
        fp = {'cname_match': 'suffix', 'cname': ['.example.com']}
        result = match_cname('', fp)
        self.assertIsNone(result)

    def test_match_cname_invalid_type(self):
        fp = {'cname_match': 'suffix', 'cname': ['.example.com']}
        result = match_cname(None, fp)
        self.assertIsNone(result)


from unittest.mock import patch, MagicMock, AsyncMock
from modules.takeover.takeover import TakeoverResult, TakeoverCheck


class TestTakeoverResult(unittest.TestCase):
    """TakeoverResult dataclass 测试"""

    def test_dataclass_defaults(self):
        r = TakeoverResult(subdomain='test.example.com')
        self.assertEqual(r.status, 'not_vulnerable')
        self.assertIsNone(r.cname)

    def test_dataclass_full(self):
        r = TakeoverResult(
            subdomain='test.example.com',
            cname='test.github.io',
            service='github-pages',
            severity='high',
            status='vulnerable',
            detail={'http_status': 404}
        )
        self.assertEqual(r.service, 'github-pages')
        self.assertEqual(r.detail['http_status'], 404)


class TestTakeoverDNS(unittest.TestCase):
    """DNS 解析和 CNAME 缓存测试"""

    def setUp(self):
        TakeoverCheck._resolve_cname.cache_clear()

    @patch.object(dns.resolver.Resolver, 'resolve')
    def test_resolve_cname_success(self, mock_resolve):
        mock_answer = MagicMock()
        mock_answer.target = 'test.github.io.'
        mock_resolve.return_value = [mock_answer]

        check = TakeoverCheck('example.com')
        cname, status = TakeoverCheck._resolve_cname('test.example.com')
        self.assertEqual(cname, 'test.github.io')
        self.assertEqual(status, 'NOERROR')

    @patch.object(dns.resolver.Resolver, 'resolve')
    def test_resolve_cname_nxdomain(self, mock_resolve):
        mock_resolve.side_effect = dns.resolver.NXDOMAIN

        check = TakeoverCheck('example.com')
        cname, status = check._resolve_cname('nonexistent.example.com')
        self.assertIsNone(cname)
        self.assertEqual(status, 'NXDOMAIN')

    @patch.object(dns.resolver.Resolver, 'resolve')
    def test_resolve_cname_noanswer(self, mock_resolve):
        mock_resolve.side_effect = dns.resolver.NoAnswer

        check = TakeoverCheck('example.com')
        cname, status = check._resolve_cname('test.example.com')
        self.assertIsNone(cname)
        self.assertEqual(status, 'NOERROR')


class TestTakeoverCheckSubdomain(unittest.TestCase):
    """check_subdomain 方法和 run 方法的测试"""

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    def test_no_cname(self, mock_resolve):
        mock_resolve.return_value = (None, 'NOERROR')
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'not_vulnerable')
        self.assertIsNone(result.cname)

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    def test_cname_no_match(self, mock_resolve):
        mock_resolve.return_value = ('test.unknown-service.com.', 'NOERROR')
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'not_vulnerable')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    def test_nxdomain(self, mock_resolve):
        mock_resolve.return_value = (None, 'NXDOMAIN')
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'not_vulnerable')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    def test_timeout(self, mock_resolve):
        mock_resolve.return_value = (None, 'TIMEOUT')
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'error')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    def test_dns_error(self, mock_resolve):
        mock_resolve.return_value = (None, 'ERROR:SERVFAIL')
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'error')
        self.assertIn('SERVFAIL', result.detail['dns_status'])

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    @patch('modules.takeover.takeover.TakeoverCheck._check_http')
    def test_matched_cname_routes_to_http(self, mock_http, mock_resolve):
        mock_resolve.return_value = ('test.github.io', 'NOERROR')
        mock_http.return_value = {
            'judgment': 'vulnerable', 'http_status': 404,
            'http_path': '/', 'matched_fingerprints': ['GitHub Pages'],
            'missed_fingerprints': [], 'http_error': None,
        }
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'vulnerable')
        self.assertEqual(result.service, 'github-pages')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    @patch('modules.takeover.takeover.TakeoverCheck._apply_http_check')
    def test_run_async_batch(self, mock_http, mock_resolve):
        import asyncio
        mock_resolve.return_value = ('test.github.io', 'NOERROR')
        mock_http.return_value = TakeoverResult(
            subdomain='test.example.com', cname='test.github.io.',
            service='github-pages', status='vulnerable'
        )
        check = TakeoverCheck('example.com')
        results = asyncio.run(check.run({'test.example.com'}))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, 'vulnerable')


import aiohttp


class TestTakeoverHTTP(unittest.TestCase):
    """HTTP 指纹检查和判定逻辑测试"""

    def setUp(self):
        self.check = TakeoverCheck('example.com')

    def test_fingerprint_match_body_success(self):
        http_check = {
            'fingerprints': [
                {'type': 'body', 'pattern': 'NoSuchBucket', 'required': True}
            ],
            'status_codes': [404],
        }
        resp = {'status_code': 404, 'body': 'The specified bucket does not exist NoSuchBucket', 'headers': {}}
        status_match, matched, missed = self.check._check_fingerprint_match(http_check, resp)
        self.assertTrue(status_match)
        self.assertIn('NoSuchBucket', matched)

    def test_fingerprint_match_body_fail(self):
        http_check = {
            'fingerprints': [
                {'type': 'body', 'pattern': 'NoSuchBucket', 'required': True}
            ],
            'status_codes': [404],
        }
        resp = {'status_code': 404, 'body': 'Welcome to nginx', 'headers': {}}
        status_match, matched, missed = self.check._check_fingerprint_match(http_check, resp)
        self.assertTrue(status_match)
        self.assertNotIn('NoSuchBucket', matched)

    def test_fingerprint_status_mismatch(self):
        http_check = {
            'fingerprints': [
                {'type': 'body', 'pattern': 'NoSuchBucket', 'required': True}
            ],
            'status_codes': [404],
        }
        resp = {'status_code': 200, 'body': 'NoSuchBucket', 'headers': {}}
        status_match, matched, missed = self.check._check_fingerprint_match(http_check, resp)
        self.assertFalse(status_match)

    def test_judge_vulnerable_all_required_match(self):
        fp = {
            'http_check': {
                'fingerprints': [
                    {'type': 'body', 'pattern': 'NoSuchBucket', 'required': True}
                ],
            }
        }
        status = self.check._judge(fp, True, ['NoSuchBucket'], [])
        self.assertEqual(status, 'vulnerable')

    def test_judge_likely_required_miss(self):
        fp = {
            'http_check': {
                'fingerprints': [
                    {'type': 'body', 'pattern': 'NoSuchBucket', 'required': True}
                ],
            }
        }
        status = self.check._judge(fp, True, [], ['NoSuchBucket'])
        self.assertEqual(status, 'likely')

    def test_judge_likely_no_required_with_match(self):
        fp = {
            'http_check': {
                'fingerprints': [
                    {'type': 'body', 'pattern': 'something', 'required': False}
                ],
            }
        }
        status = self.check._judge(fp, True, ['something'], [])
        self.assertEqual(status, 'likely')

    def test_judge_not_vulnerable_status_mismatch(self):
        fp = {
            'http_check': {
                'fingerprints': [
                    {'type': 'body', 'pattern': 'NoSuchBucket', 'required': True}
                ],
            }
        }
        status = self.check._judge(fp, False, [], [])
        self.assertEqual(status, 'not_vulnerable')

    def test_judge_required_multiple_all_match(self):
        fp = {
            'http_check': {
                'fingerprints': [
                    {'type': 'body', 'pattern': 'NoSuchBucket', 'required': True},
                    {'type': 'header', 'pattern': 'x-amz-request-id', 'required': True},
                ],
            }
        }
        status = self.check._judge(fp, True, ['NoSuchBucket', 'x-amz-request-id'], [])
        self.assertEqual(status, 'vulnerable')

    def test_judge_required_multiple_partial_match(self):
        fp = {
            'http_check': {
                'fingerprints': [
                    {'type': 'body', 'pattern': 'NoSuchBucket', 'required': True},
                    {'type': 'header', 'pattern': 'x-amz-request-id', 'required': True},
                ],
            }
        }
        status = self.check._judge(fp, True, ['NoSuchBucket'], ['x-amz-request-id'])
        self.assertEqual(status, 'likely')


class TestTakeoverHTTPIntegration(unittest.TestCase):
    """HTTP 确认全链路测试（mock）"""

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    @patch('modules.takeover.takeover.TakeoverCheck._check_http')
    def test_vulnerable_full_flow(self, mock_http, mock_resolve):
        mock_resolve.return_value = ('test.github.io', 'NOERROR')
        mock_http.return_value = {
            'http_path': '/', 'http_status': 404,
            'matched_fingerprints': ["There isn't a GitHub Pages site here"],
            'missed_fingerprints': [],
            'judgment': 'vulnerable', 'http_error': None,
        }
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'vulnerable')
        self.assertEqual(result.service, 'github-pages')
        self.assertEqual(result.severity, 'high')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    @patch('modules.takeover.takeover.TakeoverCheck._check_http')
    def test_likely_flow(self, mock_http, mock_resolve):
        mock_resolve.return_value = ('test.github.io', 'NOERROR')
        mock_http.return_value = {
            'http_path': '/', 'http_status': 404,
            'matched_fingerprints': [],
            'missed_fingerprints': ["There isn't a GitHub Pages site here"],
            'judgment': 'likely', 'http_error': None,
        }
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'likely')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    @patch('modules.takeover.takeover.TakeoverCheck._check_http')
    def test_not_vulnerable_flow(self, mock_http, mock_resolve):
        mock_resolve.return_value = ('test.github.io', 'NOERROR')
        mock_http.return_value = {
            'http_path': '/', 'http_status': 200,
            'matched_fingerprints': [],
            'missed_fingerprints': [],
            'judgment': 'not_vulnerable', 'http_error': None,
        }
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'not_vulnerable')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    @patch('modules.takeover.takeover.TakeoverCheck._check_http')
    def test_unknown_flow(self, mock_http, mock_resolve):
        mock_resolve.return_value = ('test.github.io', 'NOERROR')
        mock_http.return_value = {
            'http_path': '/', 'http_status': 0,
            'matched_fingerprints': [],
            'missed_fingerprints': [],
            'judgment': 'unknown', 'http_error': 'timeout',
        }
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'unknown')

    def test_takeover_run_output_format(self):
        """验证 takeover_run 返回正确的字典格式"""
        import asyncio
        from modules.takeover import takeover_run
        with patch.object(TakeoverCheck, 'run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = [
                TakeoverResult(
                    subdomain='test.example.com', cname='test.github.io.',
                    service='github-pages', severity='high',
                    status='vulnerable', detail={'http_status': 404}
                )
            ]
            results = takeover_run('example.com', {'test.example.com'})
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['status'], 'vulnerable')
            self.assertIn('subdomain', results[0])
            self.assertIn('cname', results[0])
            self.assertIn('service', results[0])
            self.assertIn('severity', results[0])
            self.assertIn('status', results[0])
            self.assertIn('detail', results[0])
        # 清理 takeover_run 关闭的事件循环，避免影响后续测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


if __name__ == '__main__':
    unittest.main()
