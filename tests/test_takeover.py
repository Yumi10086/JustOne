# -*- coding: utf-8 -*-
"""
子域名接管检测模块测试
"""

import json
from pathlib import Path
import unittest

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


if __name__ == '__main__':
    unittest.main()
