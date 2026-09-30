"""
Unit tests for justone.py CLI
"""

import unittest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


import pytest

# 真实网络依赖（搜索引擎/证书日志/DNS 流量/CLI 端到端）：CI 默认跳过，
# 本地用 pytest -m network 单独运行，或 pytest 全量运行
pytestmark = pytest.mark.network
class TestJustOneCLI(unittest.TestCase):
    """测试 justone.py CLI 入口"""

    def setUp(self):
        self.project_root = Path(__file__).parent.parent

    def test_version_variable_exists(self):
        """测试版本变量存在"""
        from justone import __version__
        self.assertEqual(__version__, "1.0.0")

    def test_app_exists(self):
        """测试 app 存在"""
        from justone import app
        self.assertIsNotNone(app)

    def test_import_modules(self):
        """测试导入主要模块"""
        from justone import Collect, Brute, export_subdomains, export_results, Domain
        self.assertIsNotNone(Collect)
        self.assertIsNotNone(Brute)
        self.assertIsNotNone(export_subdomains)
        self.assertIsNotNone(export_results)
        self.assertIsNotNone(Domain)

    def test_main_function_exists(self):
        """测试 main 函数存在"""
        from justone import main
        self.assertTrue(callable(main))

    def test_check_function_exists(self):
        """测试 check 函数存在"""
        from justone import check
        self.assertTrue(callable(check))

    def test_brute_function_exists(self):
        """测试 brute 函数存在"""
        from justone import brute
        self.assertTrue(callable(brute))

    def test_typer_invoke(self):
        """测试 Typer 命令调用"""
        from typer.testing import CliRunner
        from justone import app

        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("JustOne", result.output)

    def test_typer_main_help(self):
        """测试 main 命令帮助"""
        from typer.testing import CliRunner
        from justone import app

        runner = CliRunner()
        result = runner.invoke(app, ["main", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("目标域名", result.output)

    def test_typer_brute_help(self):
        """测试 brute 命令帮助"""
        from typer.testing import CliRunner
        from justone import app

        runner = CliRunner()
        result = runner.invoke(app, ["brute", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("爆破", result.output)

    def test_typer_check_help(self):
        """测试 check 命令帮助"""
        from typer.testing import CliRunner
        from justone import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("存活", result.output)

    def test_main_command_all_disabled(self):
        """测试 main 命令所有模块禁用"""
        from typer.testing import CliRunner
        from justone import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "main", "example.com",
            "--no-brute", "--no-search", "--no-cert", "--no-dataset"
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("未发现子域名", result.output)

    def test_main_command_with_output(self):
        """测试 main 命令输出到文件"""
        from typer.testing import CliRunner
        from justone import app

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output.csv"
            runner = CliRunner()
            result = runner.invoke(app, [
                "main", "example.com",
                "--no-brute", "--no-search", "--no-cert", "--no-dataset",
                "-o", str(output_path)
            ])
            self.assertEqual(result.exit_code, 0)

    def test_brute_command_basic(self):
        """测试 brute 命令基本功能（跳过，避免网络超时）"""
        self.skipTest("Skipped to avoid network timeout")

    def test_brute_command_with_wordlist(self):
        """测试 brute 命令带字典参数"""
        from typer.testing import CliRunner
        from justone import app

        runner = CliRunner()
        result = runner.invoke(app, ["brute", "example.com", "--wordlist", "/nonexistent.txt"])
        self.assertIn("爆破", result.output)

    def test_check_command_basic(self):
        """测试 check 命令基本功能"""
        from typer.testing import CliRunner
        from justone import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "example.com"])
        self.assertEqual(result.exit_code, 0)

    def test_check_excludes_wildcard(self):
        """测试 check 在存活检查前排除泛解析子域名（-i 模式，mock 网络）"""
        from typer.testing import CliRunner
        from justone import app
        from common.wildcard import WildcardInfo

        with tempfile.TemporaryDirectory() as tmpdir:
            subs_file = Path(tmpdir) / "subs.txt"
            subs_file.write_text(
                "wild.example.com\nreal.example.com\n", encoding='utf-8'
            )
            out_file = Path(tmpdir) / "out.csv"

            runner = CliRunner()
            with patch('common.wildcard.detect_and_filter') as mock_daf, \
                 patch('modules.check.DNSCheck') as mock_dns:
                mock_daf.return_value = (
                    {'real.example.com'},
                    {'wild.example.com'},
                    WildcardInfo(domain='example.com', detected=True, ips={'1.2.3.4'}),
                )
                mock_dns.return_value.run.return_value = [
                    {'subdomain': 'real.example.com', 'ip': '9.9.9.9', 'resolve': True}
                ]
                result = runner.invoke(app, [
                    "check", "-i", str(subs_file), "--dns", "-o", str(out_file)
                ])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("泛解析", result.output)
        self.assertIn("排除", result.output)
        # 泛解析域名不应进入存活检查
        passed_subdomains = mock_dns.return_value.run.call_args[0][0]
        self.assertNotIn('wild.example.com', passed_subdomains)
        self.assertIn('real.example.com', passed_subdomains)

    def test_check_no_wildcard_flag(self):
        """测试 --no-wildcard 跳过泛解析检测"""
        from typer.testing import CliRunner
        from justone import app

        with tempfile.TemporaryDirectory() as tmpdir:
            subs_file = Path(tmpdir) / "subs.txt"
            subs_file.write_text("real.example.com\n", encoding='utf-8')
            out_file = Path(tmpdir) / "out.csv"

            runner = CliRunner()
            with patch('common.wildcard.detect_and_filter') as mock_daf, \
                 patch('modules.check.DNSCheck') as mock_dns:
                mock_dns.return_value.run.return_value = []
                result = runner.invoke(app, [
                    "check", "-i", str(subs_file), "--dns",
                    "--no-wildcard", "-o", str(out_file)
                ])

        self.assertEqual(result.exit_code, 0)
        mock_daf.assert_not_called()


class TestDomainParsing(unittest.TestCase):
    """测试域名解析功能"""

    def test_domain_registered(self):
        """测试注册域名提取"""
        from common.domain import Domain

        d = Domain("www.example.com")
        self.assertEqual(d.registered(), "example.com")

    def test_domain_with_subdomain(self):
        """测试带子域名的域名"""
        from common.domain import Domain

        d = Domain("blog.test.example.com")
        self.assertEqual(d.registered(), "example.com")

    def test_domain_invalid(self):
        """测试无效域名"""
        from common.domain import Domain

        d = Domain("invalid")
        self.assertIsNone(d.registered())


class TestCollectModule(unittest.TestCase):
    """测试 Collect 模块"""

    def test_collect_init(self):
        """测试收集器初始化"""
        from modules.collect import Collect

        collect = Collect("example.com")
        self.assertIsNotNone(collect.registered_domain)
        self.assertEqual(collect.registered_domain, "example.com")

    def test_collect_no_modules(self):
        """测试禁用所有模块的收集"""
        from modules.collect import Collect

        collect = Collect("example.com", {
            'enable_search': False,
            'enable_certificate': False,
            'enable_dataset': False,
            'enable_intelligence': False,
        })
        result = collect.run()
        self.assertEqual(len(result), 0)


class TestBruteModule(unittest.TestCase):
    """测试 Brute 模块"""

    def test_brute_init(self):
        """测试爆破模块初始化"""
        from modules.brute import Brute

        brute = Brute("example.com")
        self.assertEqual(brute.domain, "example.com")

    def test_brute_run_invalid_wordlist(self):
        """测试无效字典路径"""
        from modules.brute import Brute

        brute = Brute("example.com", {'wordlist': '/invalid/path.txt'})
        result = brute.run()
        self.assertEqual(len(result), 0)


class TestExportModule(unittest.TestCase):
    """测试导出模块"""

    def test_export_subdomains_to_file(self):
        """测试导出子域名到文件"""
        from modules.export import export_subdomains

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdomains.txt"
            subdomains = ["www.example.com", "mail.example.com"]
            result = export_subdomains(subdomains, output_path, "txt")
            self.assertTrue(result)
            self.assertTrue(output_path.exists())

            content = output_path.read_text()
            self.assertIn("www.example.com", content)

    def test_export_results_csv(self):
        """测试导出 CSV 格式"""
        from modules.export import export_results

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.csv"
            results = [
                {'subdomain': 'www.example.com', 'ip': '1.2.3.4'},
                {'subdomain': 'mail.example.com', 'ip': '5.6.7.8'},
            ]
            result = export_results(results, output_path, "csv")
            self.assertTrue(result)
            self.assertTrue(output_path.exists())

    def test_export_empty_results(self):
        """测试导出空结果"""
        from modules.export import export_results

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "empty.csv"
            result = export_results([], output_path, "csv")
            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()