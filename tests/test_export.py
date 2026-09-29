"""
Unit tests for modules/export.py
"""

import unittest
import sys
import os
import tempfile
import json
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.export import (
    export_results,
    export_subdomains,
    results_to_dict,
    export_config,
    set_export_config,
)


class TestExportConfig(unittest.TestCase):
    """测试导出模块配置函数"""

    def test_default_config(self):
        """测试默认配置"""
        self.assertEqual(export_config['default_format'], 'csv')
        self.assertIsNone(export_config['default_output_dir'])

    def test_set_export_config(self):
        """测试设置配置"""
        original = export_config.copy()
        try:
            set_export_config({'default_format': 'json'})
            self.assertEqual(export_config['default_format'], 'json')
        finally:
            export_config.update(original)


class TestExportResults(unittest.TestCase):
    """测试 export_results 函数"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.results = [
            {'subdomain': 'www.example.com', 'ip': '1.2.3.4', 'module': 'test'},
            {'subdomain': 'mail.example.com', 'ip': '5.6.7.8', 'module': 'test'},
        ]

    def tearDown(self):
        for f in Path(self.temp_dir).glob('*'):
            f.unlink()
        os.rmdir(self.temp_dir)

    def test_export_csv(self):
        """测试导出 CSV 格式"""
        output = Path(self.temp_dir) / 'result.csv'
        result = export_results(self.results, output, 'csv')
        self.assertTrue(result)
        self.assertTrue(output.exists())
        with open(output, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)

    def test_export_json(self):
        """测试导出 JSON 格式"""
        output = Path(self.temp_dir) / 'result.json'
        result = export_results(self.results, output, 'json')
        self.assertTrue(result)
        self.assertTrue(output.exists())
        with open(output, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)

    def test_export_empty_results(self):
        """测试导出空结果"""
        output = Path(self.temp_dir) / 'empty.csv'
        result = export_results([], output, 'csv')
        self.assertFalse(result)

    def test_export_case_insensitive_format(self):
        """测试格式大小写不敏感"""
        output = Path(self.temp_dir) / 'result.CSV'
        result = export_results(self.results, output, 'CSV')
        self.assertTrue(result)


class TestExportSubdomains(unittest.TestCase):
    """测试 export_subdomains 函数"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.subdomains = ['www.example.com', 'mail.example.com', 'ftp.example.com']

    def tearDown(self):
        for f in Path(self.temp_dir).glob('*'):
            f.unlink()
        os.rmdir(self.temp_dir)

    def test_export_txt(self):
        """测试导出文本格式"""
        output = Path(self.temp_dir) / 'subdomains.txt'
        result = export_subdomains(self.subdomains, output, 'txt')
        self.assertTrue(result)
        self.assertTrue(output.exists())
        with open(output, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 3)

    def test_export_txt_json(self):
        """测试导出 JSON 格式"""
        output = Path(self.temp_dir) / 'subdomains.json'
        result = export_subdomains(self.subdomains, output, 'json')
        self.assertTrue(result)
        self.assertTrue(output.exists())
        with open(output, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(len(data), 3)

    def test_export_empty_subdomains(self):
        """测试导出空子域名列表"""
        output = Path(self.temp_dir) / 'empty.txt'
        result = export_subdomains([], output, 'txt')
        self.assertFalse(result)

    def test_export_txt_default_format(self):
        """测试默认导出文本格式"""
        output = Path(self.temp_dir) / 'default.txt'
        result = export_subdomains(self.subdomains, output)
        self.assertTrue(result)


class TestResultsToDict(unittest.TestCase):
    """测试 results_to_dict 函数"""

    def test_basic_conversion(self):
        """测试基本转换"""
        subdomains = ['www.example.com', 'mail.example.com']
        result = results_to_dict(subdomains, 'test_module')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['subdomain'], 'www.example.com')
        self.assertEqual(result[0]['module'], 'test_module')

    def test_empty_list(self):
        """测试空列表"""
        result = results_to_dict([], 'test')
        self.assertEqual(len(result), 0)

    def test_default_module_name(self):
        """测试默认模块名称"""
        subdomains = ['www.example.com']
        result = results_to_dict(subdomains)
        self.assertEqual(result[0]['module'], 'unknown')


if __name__ == '__main__':
    unittest.main()