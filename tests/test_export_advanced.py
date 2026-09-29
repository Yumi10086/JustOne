"""
Unit tests for modules/export.py - export functionality
"""

import unittest
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.export import export_results, export_subdomains


class TestExportResults(unittest.TestCase):
    """测试 export_results 函数"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_results = [
            {'subdomain': 'www.example.com', 'status': 200},
            {'subdomain': 'api.example.com', 'status': 404},
        ]

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_csv(self):
        """测试 CSV 导出"""
        output = Path(self.temp_dir) / 'result.csv'
        result = export_results(self.test_results, output, 'csv')
        self.assertTrue(result)
        self.assertTrue(output.exists())
        content = output.read_text(encoding='utf-8')
        self.assertIn('www.example.com', content)
        self.assertIn('api.example.com', content)

    def test_export_json(self):
        """测试 JSON 导出"""
        output = Path(self.temp_dir) / 'result.json'
        result = export_results(self.test_results, output, 'json')
        self.assertTrue(result)
        self.assertTrue(output.exists())
        content = output.read_text(encoding='utf-8')
        self.assertIn('www.example.com', content)

    def test_export_txt_falls_back_to_csv(self):
        """测试 txt 格式回退到 CSV"""
        output = Path(self.temp_dir) / 'result.txt'
        result = export_results(self.test_results, output, 'txt')
        self.assertTrue(result)
        self.assertTrue(output.exists())

    def test_export_custom_extension(self):
        """测试自定义后缀（如 .dat）"""
        output = Path(self.temp_dir) / 'result.dat'
        result = export_results(self.test_results, output, 'dat')
        self.assertTrue(result)
        self.assertTrue(output.exists())
        content = output.read_text(encoding='utf-8')
        self.assertIn('www.example.com', content)

    def test_export_custom_extension_csv_format(self):
        """测试自定义后缀使用 CSV 格式"""
        output = Path(self.temp_dir) / 'result.custom'
        result = export_results(self.test_results, output, 'custom')
        self.assertTrue(result)
        self.assertTrue(output.exists())
        content = output.read_text(encoding='utf-8')
        self.assertIn('subdomain', content)

    def test_export_uppercase_format(self):
        """测试大写格式名"""
        output = Path(self.temp_dir) / 'result.CSV'
        result = export_results(self.test_results, output, 'CSV')
        self.assertTrue(result)
        self.assertTrue(output.exists())

    def test_export_empty_results(self):
        """测试空结果"""
        output = Path(self.temp_dir) / 'result.csv'
        result = export_results([], output, 'csv')
        self.assertFalse(result)

    def test_export_creates_parent_dir(self):
        """测试自动创建父目录"""
        output = Path(self.temp_dir) / 'subdir' / 'result.csv'
        result = export_results(self.test_results, output, 'csv')
        self.assertTrue(result)
        self.assertTrue(output.exists())


class TestExportSubdomains(unittest.TestCase):
    """测试 export_subdomains 函数"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_subdomains = ['www.example.com', 'api.example.com', 'mail.example.com']

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_txt(self):
        """测试 txt 导出"""
        output = Path(self.temp_dir) / 'subdomains.txt'
        result = export_subdomains(self.test_subdomains, output, 'txt')
        self.assertTrue(result)
        self.assertTrue(output.exists())
        content = output.read_text(encoding='utf-8')
        self.assertGreaterEqual(content.count('\n'), 2)

    def test_export_json(self):
        """测试 JSON 导出"""
        output = Path(self.temp_dir) / 'subdomains.json'
        result = export_subdomains(self.test_subdomains, output, 'json')
        self.assertTrue(result)
        self.assertTrue(output.exists())

    def test_export_default_format(self):
        """测试默认格式"""
        output = Path(self.temp_dir) / 'subdomains'
        result = export_subdomains(self.test_subdomains, output, 'txt')
        self.assertTrue(result)
        self.assertTrue(output.exists())

    def test_export_empty_subdomains(self):
        """测试空子域名列表"""
        output = Path(self.temp_dir) / 'subdomains.txt'
        result = export_subdomains([], output, 'txt')
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()