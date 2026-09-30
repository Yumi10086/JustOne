"""
Unit tests for new collection sources (wayback / commoncrawl / jsanalyse)
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from common.module import Module
from modules.datasets.wayback import Wayback
from modules.datasets.commoncrawl import CommonCrawl
from modules.datasets.jsanalyse import JSAnalyse


class TestWayback(unittest.TestCase):
    def test_query_extracts_subdomains(self):
        """CDX 返回的 URL 文本应被匹配出目标域子域"""
        fake = ('["https://sub.example.com/page"]\n'
                '["https://api.example.com/v1"]\n'
                '["https://other.com/x"]')
        with patch.object(Module, 'get', return_value=MagicMock(text=fake)):
            result = Wayback('example.com').run()
        self.assertIn('sub.example.com', result)
        self.assertIn('api.example.com', result)
        self.assertNotIn('other.com', result)

    def test_queries_both_apex_and_wildcard(self):
        """应分别查询 *.domain 与 domain 两条路径"""
        calls = []

        def fake_get(self, url, params=None, **kwargs):
            calls.append(params.get('url'))
            return MagicMock(text='["https://a.example.com/"]')

        with patch.object(Module, 'get', new=fake_get):
            Wayback('example.com').run()
        self.assertIn('*.example.com/*', calls)
        self.assertIn('example.com/*', calls)


class TestCommonCrawl(unittest.TestCase):
    COLL_JSON = json.dumps([{'cdx-api': 'https://index.commoncrawl.org/CC-MAIN-2025-30-index'}])

    def test_get_latest_index(self):
        """应取 collinfo 第一项的 cdx-api 作为索引地址"""
        with patch.object(Module, 'get', return_value=MagicMock(text=self.COLL_JSON)):
            cc = CommonCrawl('example.com')
            self.assertEqual(
                cc.get_latest_index(),
                'https://index.commoncrawl.org/CC-MAIN-2025-30-index',
            )

    def test_get_latest_index_invalid(self):
        """collinfo 解析失败应返回 None 而非抛异常"""
        with patch.object(Module, 'get', return_value=MagicMock(text='not json')):
            cc = CommonCrawl('example.com')
            self.assertIsNone(cc.get_latest_index())

    def test_query_stops_on_empty_page(self):
        """第一页有结果、第二页为空时应停止翻页"""
        page0 = '["https://a.example.com/x"]\n["https://b.example.com/y"]'
        with patch.object(Module, 'get', side_effect=[
            MagicMock(text=self.COLL_JSON),   # collinfo
            MagicMock(text=page0),            # page 0
            MagicMock(text=''),               # page 1 空 → break
        ]):
            result = CommonCrawl('example.com').run()
        self.assertIn('a.example.com', result)
        self.assertIn('b.example.com', result)


class TestJSAnalyse(unittest.TestCase):
    def test_extract_scripts_same_domain_only(self):
        """只保留目标注册域及其子域的 JS 引用"""
        html = (
            '<script src="/static/app.js"></script>'
            '<script src="//cdn.example.com/lib.js"></script>'
            '<script src="https://thirdparty.com/x.js"></script>'
            '<SCRIPT src="js/inline.js"></SCRIPT>'
        )
        urls = JSAnalyse('example.com').extract_scripts(html)
        self.assertEqual(len(urls), 3)
        self.assertIn('https://example.com/static/app.js', urls)
        self.assertIn('https://cdn.example.com/lib.js', urls)
        self.assertIn('https://example.com/js/inline.js', urls)

    def test_analyse_collects_from_js(self):
        """JS 文件内容中的子域应被收集"""
        page = '<script src="/app.js"></script>'
        js = 'var api = "https://api.example.com/v1";'
        with patch.object(Module, 'get', side_effect=[
            MagicMock(text=page),
            MagicMock(text=js),
        ]):
            result = JSAnalyse('example.com').run()
        self.assertIn('api.example.com', result)

    def test_max_scripts_limit(self):
        """js_max_scripts 配置应限制抓取的 JS 数量"""
        j = JSAnalyse('example.com', {'js_max_scripts': 3})
        self.assertEqual(j.max_scripts, 3)


class TestSortBySubdomain(unittest.TestCase):
    def test_none_subdomain_sorted_last(self):
        """subdomain 为 None 的占位行不应导致排序崩溃"""
        from common.utils import sort_by_subdomain
        data = [{'subdomain': 'b.com'}, {'subdomain': None}, {'subdomain': 'a.com'}]
        result = sort_by_subdomain(data)
        self.assertEqual([r['subdomain'] for r in result][:2], ['a.com', 'b.com'])


if __name__ == '__main__':
    unittest.main()
