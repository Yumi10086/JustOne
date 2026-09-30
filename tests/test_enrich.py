"""
tests/test_enrich.py

modules/enrich.py 的单元测试

测试覆盖范围：
- Enrich 类初始化及属性
- CDN IP CIDR 加载
- 数据库表检测与数据加载
- 记录更新
- CDN IP 识别（纯本地逻辑）
- HTTP 探测（异步静态方法）
- enrich() 三阶段管道
- run() 同步入口
- 模块级 run() 函数

运行方式:
    python -m unittest tests.test_enrich -v
"""

import asyncio
import ipaddress
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch, AsyncMock, mock_open

# 确保项目根目录在路径中，支持从 tests/ 目录运行
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import pytest

# 真实 DNS/HTTP 探测（Database/日志已 mock，但探测等真实网络超时）：CI 默认跳过
pytestmark = pytest.mark.network
class TestEnrich(unittest.TestCase):
    """Enrich 类的单元测试"""

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    def _make_record(self, rid: int = 1, subdomain: str = "test.example.com",
                     ip: str = "", status: int = None, cdn: int = None,
                     asn: str = "", **kwargs) -> Dict[str, Any]:
        """构造一条模拟记录"""
        record = {
            "id": rid,
            "subdomain": subdomain,
            "ip": ip,
            "status": status,
            "cdn": cdn,
            "asn": asn,
            "cname": "",
            "resolve": 0,
            "alive": 0,
            "title": "",
            "header": "",
            "banner": "",
            "reason": "",
            "cidr": "",
            "org": "",
        }
        record.update(kwargs)
        return record

    def _patch_cdn_load(self):
        """统一 patch CDN 文件加载，避免真实读取"""
        return patch("modules.enrich.Path.exists", return_value=False)

    # ------------------------------------------------------------------
    # setUp / tearDown
    # ------------------------------------------------------------------
    @classmethod
    def setUpClass(cls):
        """动态导入被测模块"""
        import modules.enrich as enrich_module
        cls.module = enrich_module
        cls.EnrichClass = enrich_module.Enrich

    def setUp(self):
        """每个测试前的准备工作"""
        self.patcher_logger = patch("modules.enrich.logger")
        self.mock_logger = self.patcher_logger.start()

    def tearDown(self):
        """每个测试后的清理工作"""
        self.patcher_logger.stop()

    # ==================================================================
    # 1. 初始化相关测试
    # ==================================================================

    def test_init_default_params(self):
        """测试默认参数初始化"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")

        self.assertEqual(enricher.db_path, Path("/tmp/test.db"))
        self.assertEqual(enricher.concurrent, 200)
        self.assertEqual(enricher.timeout, 10)
        self.assertIsNone(enricher._db)
        self.assertIsNone(enricher.table_name)
        self.assertIsNone(enricher.domain)
        self.assertEqual(enricher.records, [])
        self.assertEqual(enricher.cdn_ip_ranges, [])

    def test_init_custom_params(self):
        """测试自定义参数初始化"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/data/test.db", concurrent=500, timeout=30)

        self.assertEqual(enricher.concurrent, 500)
        self.assertEqual(enricher.timeout, 30)

    def test_load_cdn_ranges_success(self):
        """测试成功加载 CDN CIDR 文件"""
        mock_cidrs = ["1.2.3.0/24", "5.6.0.0/16", "2001:db8::/32"]
        m = mock_open(read_data=json.dumps(mock_cidrs))

        with patch("modules.enrich.Path.exists", return_value=True):
            with patch("modules.enrich.open", m):
                with patch("modules.enrich.Database"):
                    enricher = self.EnrichClass("/tmp/test.db")

        self.assertEqual(len(enricher.cdn_ip_ranges), 3)
        self.assertIsInstance(enricher.cdn_ip_ranges[0], ipaddress.IPv4Network)
        self.assertIsInstance(enricher.cdn_ip_ranges[2], ipaddress.IPv6Network)

    def test_load_cdn_ranges_file_not_exist(self):
        """测试 CDN CIDR 文件不存在时的情况"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")

        self.assertEqual(enricher.cdn_ip_ranges, [])

    def test_load_cdn_ranges_invalid_cidr(self):
        """测试包含无效 CIDR 时的容错处理"""
        mock_cidrs = ["1.2.3.0/24", "invalid-cidr", "5.6.0.0/16"]
        m = mock_open(read_data=json.dumps(mock_cidrs))

        with patch("modules.enrich.Path.exists", return_value=True):
            with patch("modules.enrich.open", m):
                with patch("modules.enrich.Database"):
                    enricher = self.EnrichClass("/tmp/test.db")

        self.assertEqual(len(enricher.cdn_ip_ranges), 2)

    # ==================================================================
    # 2. 数据库属性与生命周期
    # ==================================================================

    def test_db_property_lazy_load(self):
        """测试 db 属性的懒加载"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database") as MockDB:
                enricher = self.EnrichClass("/tmp/test.db")
                self.assertIsNone(enricher._db)

                _ = enricher.db  # 触发懒加载
                # Windows 下 Path 会转换分隔符，用 os.path.normpath 比较
                MockDB.assert_called_once()
                call_args = MockDB.call_args[0][0]
                self.assertEqual(os.path.normpath(call_args), os.path.normpath("/tmp/test.db"))
                self.assertIsNotNone(enricher._db)

    def test_db_property_cached(self):
        """测试 db 属性被缓存，不会重复创建"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database") as MockDB:
                enricher = self.EnrichClass("/tmp/test.db")
                db1 = enricher.db
                db2 = enricher.db
                MockDB.assert_called_once()
                self.assertIs(db1, db2)

    def test_close(self):
        """测试 close 方法正确释放资源"""
        mock_db = MagicMock()
        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                _ = enricher.db  # 先初始化
                enricher.close()

        mock_db.close.assert_called_once()
        self.assertIsNone(enricher._db)

    def test_close_without_init(self):
        """测试未初始化 db 时调用 close 不会报错"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.close()  # 不应抛出异常

    # ==================================================================
    # 3. 表检测与数据加载
    # ==================================================================

    def test_detect_table_success(self):
        """测试成功检测到最新表"""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = [["example_com"]]

        mock_db = MagicMock()
        mock_db.query.return_value = mock_result

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                table = enricher._detect_table()

        self.assertEqual(table, "example_com")
        mock_db.query.assert_called_once()

    def test_detect_table_no_result(self):
        """测试数据库无表时返回 None"""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = []

        mock_db = MagicMock()
        mock_db.query.return_value = mock_result

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                table = enricher._detect_table()

        self.assertIsNone(table)

    def test_detect_table_query_failed(self):
        """测试查询失败时返回 None"""
        mock_result = MagicMock()
        mock_result.success = False

        mock_db = MagicMock()
        mock_db.query.return_value = mock_result

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                table = enricher._detect_table()

        self.assertIsNone(table)

    def test_load_with_table_name(self):
        """测试指定表名加载数据"""
        mock_rows = [
            {"id": 1, "subdomain": "a.example.com", "ip": "1.2.3.4"},
            {"id": 2, "subdomain": "b.example.com", "ip": ""},
        ]
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = mock_rows

        mock_db = MagicMock()
        mock_db.get_data.return_value = mock_result

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                records = enricher.load("example_com")

        self.assertEqual(enricher.table_name, "example_com")
        self.assertEqual(enricher.domain, "example.com")
        self.assertEqual(len(records), 2)
        self.assertEqual(enricher.records, records)

    def test_load_auto_detect_table(self):
        """测试自动检测表名加载数据"""
        mock_detect = MagicMock()
        mock_detect.success = True
        mock_detect.data = [["test_com"]]

        mock_rows = [{"id": 1, "subdomain": "a.test.com", "ip": "1.1.1.1"}]
        mock_data = MagicMock()
        mock_data.success = True
        mock_data.data = mock_rows

        mock_db = MagicMock()
        mock_db.query.return_value = mock_detect
        mock_db.get_data.return_value = mock_data

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                records = enricher.load()

        self.assertEqual(enricher.table_name, "test_com")
        self.assertEqual(enricher.domain, "test.com")

    def test_load_no_table_found(self):
        """测试无可用表时返回空列表"""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = []

        mock_db = MagicMock()
        mock_db.query.return_value = mock_result

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                records = enricher.load()

        self.assertEqual(records, [])
        self.assertEqual(enricher.records, [])

    def test_load_empty_data(self):
        """测试表存在但无数据的情况"""
        mock_detect = MagicMock()
        mock_detect.success = True
        mock_detect.data = [["example_com"]]

        mock_data = MagicMock()
        mock_data.success = True
        mock_data.data = []

        mock_db = MagicMock()
        mock_db.query.return_value = mock_detect
        mock_db.get_data.return_value = mock_data

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                records = enricher.load()

        self.assertEqual(records, [])

    # ==================================================================
    # 4. 记录更新
    # ==================================================================

    def test_update_record_success(self):
        """测试成功更新单条记录"""
        mock_result = MagicMock()
        mock_result.success = True

        mock_db = MagicMock()
        mock_db.query.return_value = mock_result

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.table_name = "example_com"
                ok = enricher._update_record(1, {"ip": "1.2.3.4", "status": 200})

        self.assertTrue(ok)
        mock_db.query.assert_called_once()
        call_args = mock_db.query.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        self.assertIn("UPDATE", sql.upper())
        self.assertIn("example_com", sql)
        self.assertEqual(params, ("1.2.3.4", 200, 1))

    def test_update_record_empty_data(self):
        """测试空数据不执行更新"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                ok = enricher._update_record(1, {})
        self.assertFalse(ok)

    def test_update_record_no_table(self):
        """测试未设置表名时不执行更新"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                ok = enricher._update_record(1, {"ip": "1.2.3.4"})
        self.assertFalse(ok)

    def test_update_record_sql_injection_protection(self):
        """测试表名中的双引号被正确转义/移除"""
        mock_result = MagicMock()
        mock_result.success = True

        mock_db = MagicMock()
        mock_db.query.return_value = mock_result

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.table_name = 'example"_com'
                enricher._update_record(1, {"ip": "1.2.3.4"})

        sql = mock_db.query.call_args[0][0]
        self.assertNotIn('""', sql)  # 双引号已被移除

    # ==================================================================
    # 5. CDN IP 识别（纯本地逻辑）
    # ==================================================================

    def test_is_cdn_ip_true(self):
        """测试命中 CDN IP 段返回 True"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.cdn_ip_ranges = [ipaddress.ip_network("1.2.3.0/24")]

        self.assertTrue(enricher._is_cdn_ip("1.2.3.100"))

    def test_is_cdn_ip_false(self):
        """测试非 CDN IP 返回 False"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.cdn_ip_ranges = [ipaddress.ip_network("1.2.3.0/24")]

        self.assertFalse(enricher._is_cdn_ip("5.6.7.8"))

    def test_is_cdn_ip_invalid_ip(self):
        """测试无效 IP 返回 False 不抛异常"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.cdn_ip_ranges = [ipaddress.ip_network("1.2.3.0/24")]

        self.assertFalse(enricher._is_cdn_ip("not-an-ip"))
        self.assertFalse(enricher._is_cdn_ip(""))

    def test_is_cdn_ip_ipv6(self):
        """测试 IPv6 CDN 识别"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.cdn_ip_ranges = [ipaddress.ip_network("2001:db8::/32")]

        self.assertTrue(enricher._is_cdn_ip("2001:db8::1"))
        self.assertFalse(enricher._is_cdn_ip("2001:db9::1"))

    def test_is_cdn_ip_empty_ranges(self):
        """测试空 CDN 列表时返回 False"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")

        self.assertFalse(enricher._is_cdn_ip("1.2.3.4"))

    def test_is_cdn_ip_with_whitespace(self):
        """测试带空格的 IP 字符串"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.cdn_ip_ranges = [ipaddress.ip_network("1.2.3.0/24")]

        self.assertTrue(enricher._is_cdn_ip("  1.2.3.100  "))

    # ==================================================================
    # 6. HTTP 探测（异步静态方法）
    # ==================================================================

    def test_http_probe_no_ip(self):
        """测试无 IP 时直接返回空结果"""
        async def _test():
            mock_session = MagicMock()
            result = await self.EnrichClass._http_probe(
                "test.example.com", mock_session, 10, ip=""
            )
            self.assertIsNone(result["status"])
            self.assertEqual(result["alive"], 0)
            self.assertEqual(result["title"], "")
            mock_session.get.assert_not_called()

        asyncio.run(_test())

    def test_http_probe_success_http(self):
        """测试 HTTP 探测成功（200 OK）"""
        async def _test():
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {"Server": "nginx", "Content-Type": "text/html"}
            mock_resp.read = AsyncMock(return_value=b"<html><title>Test Page</title></html>")

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock(return_value=False)
            ))

            with patch("modules.enrich.utils") as mock_utils:
                mock_utils.get_sample_banner.return_value = "nginx"
                result = await self.EnrichClass._http_probe(
                    "test.example.com", mock_session, 10, ip="1.2.3.4"
                )

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["alive"], 1)
            self.assertEqual(result["title"], "Test Page")
            self.assertIn("Server", result["header"])

        asyncio.run(_test())

    def test_http_probe_success_https_fallback(self):
        """测试 HTTP 失败后 HTTPS 成功（HTTP 返回非 alive 状态码）"""
        async def _test():
            # 999 不在 ALIVE_CODES 中，会跳过 HTTP 尝试 HTTPS
            http_resp = AsyncMock()
            http_resp.status = 999
            http_resp.headers = {}
            http_resp.read = AsyncMock(return_value=b"")

            https_resp = AsyncMock()
            https_resp.status = 200
            https_resp.headers = {"Server": "apache"}
            https_resp.read = AsyncMock(return_value=b"<title>HTTPS OK</title>")

            mock_session = MagicMock()
            mock_session.get = MagicMock(side_effect=[
                AsyncMock(__aenter__=AsyncMock(return_value=http_resp), __aexit__=AsyncMock()),
                AsyncMock(__aenter__=AsyncMock(return_value=https_resp), __aexit__=AsyncMock())
            ])

            with patch("modules.enrich.utils") as mock_utils:
                mock_utils.get_sample_banner.return_value = "apache"
                result = await self.EnrichClass._http_probe(
                    "test.example.com", mock_session, 10, ip="1.2.3.4"
                )

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["title"], "HTTPS OK")

        asyncio.run(_test())

    def test_http_probe_timeout(self):
        """测试请求超时处理"""
        async def _test():
            mock_session = MagicMock()
            mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())

            result = await self.EnrichClass._http_probe(
                "test.example.com", mock_session, 10, ip="1.2.3.4"
            )
            self.assertIsNone(result["status"])
            self.assertEqual(result["alive"], 0)

        asyncio.run(_test())

    def test_http_probe_client_error(self):
        """测试 aiohttp 客户端错误处理"""
        import aiohttp

        async def _test():
            mock_session = MagicMock()
            mock_session.get = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))

            result = await self.EnrichClass._http_probe(
                "test.example.com", mock_session, 10, ip="1.2.3.4"
            )
            self.assertIsNone(result["status"])
            self.assertEqual(result["alive"], 0)

        asyncio.run(_test())

    def test_http_probe_non_alive_status(self):
        """测试非存活状态码（如 999）不计入 alive"""
        async def _test():
            mock_resp = AsyncMock()
            mock_resp.status = 999
            mock_resp.headers = {}
            mock_resp.read = AsyncMock(return_value=b"")

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock()
            ))

            result = await self.EnrichClass._http_probe(
                "test.example.com", mock_session, 10, ip="1.2.3.4"
            )
            self.assertIsNone(result["status"])
            self.assertEqual(result["alive"], 0)

        asyncio.run(_test())

    def test_http_probe_multiple_ips(self):
        """测试多 IP 时取第一个"""
        async def _test():
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {}
            mock_resp.read = AsyncMock(return_value=b"<title>OK</title>")

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock()
            ))

            with patch("modules.enrich.utils") as mock_utils:
                mock_utils.get_sample_banner.return_value = ""
                result = await self.EnrichClass._http_probe(
                    "test.example.com", mock_session, 10, ip="1.2.3.4,5.6.7.8"
                )

            self.assertEqual(result["status"], 200)
            # 验证 URL 使用的是第一个 IP
            call_args = mock_session.get.call_args
            self.assertIn("1.2.3.4", call_args[0][0])

        asyncio.run(_test())

    def test_http_probe_title_decode_error(self):
        """测试标题解码错误时不会崩溃"""
        async def _test():
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {}
            # 包含非法 UTF-8 序列
            mock_resp.read = AsyncMock(return_value=b"<title>\xff\xfe</title>")

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock()
            ))

            with patch("modules.enrich.utils") as mock_utils:
                mock_utils.get_sample_banner.return_value = ""
                result = await self.EnrichClass._http_probe(
                    "test.example.com", mock_session, 10, ip="1.2.3.4"
                )

            self.assertEqual(result["status"], 200)
            # 应能成功解码，使用 replacement 字符
            self.assertIsNotNone(result["title"])

        asyncio.run(_test())

    def test_http_probe_header_truncation(self):
        """测试响应头超过 2000 字符被截断"""
        async def _test():
            long_value = "x" * 3000
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {"X-Long": long_value}
            mock_resp.read = AsyncMock(return_value=b"")

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_resp),
                __aexit__=AsyncMock()
            ))

            with patch("modules.enrich.utils") as mock_utils:
                mock_utils.get_sample_banner.return_value = ""
                result = await self.EnrichClass._http_probe(
                    "test.example.com", mock_session, 10, ip="1.2.3.4"
                )

            self.assertEqual(len(result["header"]), 2000)

        asyncio.run(_test())

    # ==================================================================
    # 7. enrich() 方法（三阶段管道）
    # ==================================================================

    def test_enrich_no_records(self):
        """测试无记录时直接返回 0"""
        async def _test():
            with self._patch_cdn_load():
                with patch("modules.enrich.Database"):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.records = []
                    result = await enricher.enrich(show_progress=False)
                    self.assertEqual(result, 0)

        asyncio.run(_test())

    def test_enrich_phase1_dns_resolution(self):
        """测试阶段 1：DNS 解析（含 Phase 3 联动）"""
        async def _test():
            mock_db = MagicMock()
            mock_db.query.return_value = MagicMock(success=True)

            mock_dns_info = {
                "resolve": 1, "alive": 1,
                "ip": "1.2.3.4", "cname": "", "reason": ""
            }

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip=""),
                        self._make_record(2, "b.test.com", ip="", status=200),
                    ]

                    with patch("modules.enrich.dns_resolve.resolve_domain", return_value=mock_dns_info):
                        with patch("modules.enrich.IPAsnInfo") as MockAsn:
                            mock_asn_instance = MagicMock()
                            mock_asn_instance.find.return_value = None
                            MockAsn.return_value = mock_asn_instance

                            result = await enricher.enrich(show_progress=False)

            # Phase 1: 2 条 DNS 更新 + Phase 3: 2 条 IP 丰富（无 CDN/ASN 命中）= 2
            self.assertEqual(result, 2)
            self.assertEqual(enricher.records[0]["ip"], "1.2.3.4")

        asyncio.run(_test())

    def test_enrich_phase1_dns_skip_when_has_ip(self):
        """测试已有 IP 的记录跳过 DNS 阶段，但 Phase 3 可能触发"""
        async def _test():
            mock_db = MagicMock()
            mock_db.query.return_value = MagicMock(success=True)

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip="1.2.3.4"),
                    ]

                    with patch("modules.enrich.dns_resolve.resolve_domain") as mock_dns:
                        with patch("modules.enrich.IPAsnInfo") as MockAsn:
                            mock_asn_instance = MagicMock()
                            mock_asn_instance.find.return_value = None
                            MockAsn.return_value = mock_asn_instance

                            result = await enricher.enrich(show_progress=False)
                            mock_dns.assert_not_called()

            # Phase 3 也无 ASN 命中，返回 0
            self.assertEqual(result, 0)

        asyncio.run(_test())

    def test_enrich_phase2_http_probe(self):
        """测试阶段 2：HTTP 探测（含 Phase 3 联动）"""
        async def _test():
            mock_db = MagicMock()
            mock_db.query.return_value = MagicMock(success=True)

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip="1.2.3.4"),
                    ]

                    mock_http_result = {
                        "status": 200, "alive": 1,
                        "title": "Test", "header": "{}", "banner": "nginx"
                    }

                    with patch.object(self.EnrichClass, "_http_probe", return_value=mock_http_result):
                        with patch("modules.enrich.IPAsnInfo") as MockAsn:
                            mock_asn_instance = MagicMock()
                            mock_asn_instance.find.return_value = None
                            MockAsn.return_value = mock_asn_instance

                            result = await enricher.enrich(show_progress=False)

            # Phase 2: 1 条 HTTP 更新 + Phase 3: 无 CDN/ASN 命中 = 1
            self.assertEqual(result, 1)
            self.assertEqual(enricher.records[0]["status"], 200)
            self.assertEqual(enricher.records[0]["title"], "Test")

        asyncio.run(_test())

    def test_enrich_phase2_skip_when_has_status(self):
        """测试已有 status 的记录跳过 HTTP 阶段"""
        async def _test():
            mock_db = MagicMock()

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip="1.2.3.4", status=200),
                    ]

                    with patch.object(self.EnrichClass, "_http_probe") as mock_http:
                        with patch("modules.enrich.IPAsnInfo") as MockAsn:
                            mock_asn_instance = MagicMock()
                            mock_asn_instance.find.return_value = None
                            MockAsn.return_value = mock_asn_instance

                            result = await enricher.enrich(show_progress=False)
                            mock_http.assert_not_called()

            # Phase 3 也无 ASN 命中，返回 0
            self.assertEqual(result, 0)

        asyncio.run(_test())

    def test_enrich_phase2_skip_no_ip(self):
        """测试无 IP 记录跳过 HTTP 阶段"""
        async def _test():
            mock_db = MagicMock()

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip=""),
                    ]

                    with patch.object(self.EnrichClass, "_http_probe") as mock_http:
                        result = await enricher.enrich(show_progress=False)
                        mock_http.assert_not_called()

            self.assertEqual(result, 0)

        asyncio.run(_test())

    def test_enrich_phase3_ip_enrichment_cdn(self):
        """测试阶段 3：CDN 识别"""
        async def _test():
            mock_db = MagicMock()
            mock_db.query.return_value = MagicMock(success=True)

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.cdn_ip_ranges = [ipaddress.ip_network("1.2.3.0/24")]
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip="1.2.3.4"),
                    ]

                    with patch("modules.enrich.IPAsnInfo") as MockAsn:
                        mock_asn_instance = MagicMock()
                        mock_asn_instance.find.return_value = None
                        MockAsn.return_value = mock_asn_instance

                        result = await enricher.enrich(show_progress=False)

            self.assertEqual(result, 1)
            self.assertEqual(enricher.records[0]["cdn"], 1)

        asyncio.run(_test())

    def test_enrich_phase3_ip_enrichment_asn(self):
        """测试阶段 3：ASN 信息查询"""
        async def _test():
            mock_db = MagicMock()
            mock_db.query.return_value = MagicMock(success=True)

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip="1.2.3.4"),
                    ]

                    mock_asn_data = {
                        "cidr": "1.2.3.0/24",
                        "asn": "AS12345",
                        "org": "Example ISP"
                    }

                    with patch("modules.enrich.IPAsnInfo") as MockAsn:
                        mock_asn_instance = MagicMock()
                        mock_asn_instance.find.return_value = mock_asn_data
                        MockAsn.return_value = mock_asn_instance

                        result = await enricher.enrich(show_progress=False)

            self.assertEqual(result, 1)
            self.assertEqual(enricher.records[0]["asn"], "AS12345")
            self.assertEqual(enricher.records[0]["org"], "Example ISP")
            self.assertEqual(enricher.records[0]["cidr"], "1.2.3.0/24")

        asyncio.run(_test())

    def test_enrich_phase3_skip_when_already_has_asn(self):
        """测试已有 ASN 记录跳过 ASN 查询"""
        async def _test():
            mock_db = MagicMock()

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip="1.2.3.4", asn="AS99999"),
                    ]

                    with patch("modules.enrich.IPAsnInfo") as MockAsn:
                        mock_asn_instance = MagicMock()
                        MockAsn.return_value = mock_asn_instance

                        result = await enricher.enrich(show_progress=False)
                        mock_asn_instance.find.assert_not_called()

            self.assertEqual(result, 0)

        asyncio.run(_test())

    def test_enrich_phase3_skip_when_already_has_cdn(self):
        """测试已有 CDN 标记记录跳过 CDN 识别"""
        async def _test():
            mock_db = MagicMock()

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.cdn_ip_ranges = [ipaddress.ip_network("1.2.3.0/24")]
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip="1.2.3.4", cdn=1),
                    ]

                    with patch("modules.enrich.IPAsnInfo") as MockAsn:
                        mock_asn_instance = MagicMock()
                        mock_asn_instance.find.return_value = None
                        MockAsn.return_value = mock_asn_instance

                        result = await enricher.enrich(show_progress=False)
                        # CDN 已标记，ASN 为空，仍会查 ASN
                        mock_asn_instance.find.assert_called_once()

            self.assertEqual(result, 0)  # ASN 返回 None，无更新

        asyncio.run(_test())

    def test_enrich_phase3_multiple_ips(self):
        """测试多 IP 记录取第一个进行 IP 丰富"""
        async def _test():
            mock_db = MagicMock()
            mock_db.query.return_value = MagicMock(success=True)

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    enricher.cdn_ip_ranges = [ipaddress.ip_network("1.2.0.0/16")]
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip="1.2.3.4,5.6.7.8"),
                    ]

                    with patch("modules.enrich.IPAsnInfo") as MockAsn:
                        mock_asn_instance = MagicMock()
                        mock_asn_instance.find.return_value = None
                        MockAsn.return_value = mock_asn_instance

                        result = await enricher.enrich(show_progress=False)

            self.assertEqual(result, 1)  # 第一个 IP 命中 CDN
            self.assertEqual(enricher.records[0]["cdn"], 1)

        asyncio.run(_test())

    def test_enrich_full_pipeline(self):
        """测试完整三阶段管道"""
        async def _test():
            mock_db = MagicMock()
            mock_db.query.return_value = MagicMock(success=True)

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db", concurrent=10)
                    enricher.table_name = "test_com"
                    enricher.cdn_ip_ranges = [ipaddress.ip_network("1.2.3.0/24")]
                    enricher.records = [
                        self._make_record(1, "a.test.com", ip=""),
                    ]

                    mock_dns = {
                        "resolve": 1, "alive": 1,
                        "ip": "1.2.3.4", "cname": "", "reason": ""
                    }
                    mock_http = {
                        "status": 200, "alive": 1,
                        "title": "Home", "header": "{}", "banner": "nginx"
                    }
                    mock_asn = {"cidr": "1.2.3.0/24", "asn": "AS12345", "org": "ISP"}

                    with patch("modules.enrich.dns_resolve.resolve_domain", return_value=mock_dns):
                        with patch.object(self.EnrichClass, "_http_probe", return_value=mock_http):
                            with patch("modules.enrich.IPAsnInfo") as MockAsn:
                                mock_asn_instance = MagicMock()
                                mock_asn_instance.find.return_value = mock_asn
                                MockAsn.return_value = mock_asn_instance

                                result = await enricher.enrich(show_progress=False)

            # DNS(1) + HTTP(1) + IP(CDN+ASN=1) = 3 次更新
            self.assertEqual(result, 3)
            record = enricher.records[0]
            self.assertEqual(record["ip"], "1.2.3.4")
            self.assertEqual(record["status"], 200)
            self.assertEqual(record["title"], "Home")
            self.assertEqual(record["cdn"], 1)
            self.assertEqual(record["asn"], "AS12345")

        asyncio.run(_test())

    def test_enrich_progress_logging(self):
        """测试进度日志输出"""
        async def _test():
            mock_db = MagicMock()
            mock_db.query.return_value = MagicMock(success=True)

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"
                    # 创建超过 500 条记录以触发进度日志
                    enricher.records = [
                        self._make_record(i, f"sub{i}.test.com", ip="")
                        for i in range(600)
                    ]

                    with patch("modules.enrich.dns_resolve.resolve_domain", return_value=None):
                        with patch.object(self.EnrichClass, "_http_probe", return_value={}):
                            with patch("modules.enrich.IPAsnInfo") as MockAsn:
                                mock_asn_instance = MagicMock()
                                mock_asn_instance.find.return_value = None
                                MockAsn.return_value = mock_asn_instance

                                await enricher.enrich(show_progress=True)

            # 验证进度日志被调用
            info_calls = [c for c in self.mock_logger.info.call_args_list if "进度" in str(c)]
            self.assertGreater(len(info_calls), 0)

        asyncio.run(_test())

    # ==================================================================
    # 8. run() 同步入口
    # ==================================================================

    def test_run_sync_success(self):
        """测试同步入口成功执行"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.load = MagicMock()
                enricher.records = [self._make_record(1, "test.com")]
                enricher.enrich = AsyncMock(return_value=5)
                enricher.close = MagicMock()

                result = enricher.run("example_com")

        self.assertEqual(result, 5)
        enricher.load.assert_called_once_with("example_com")
        enricher.enrich.assert_awaited_once()
        enricher.close.assert_called_once()

    def test_run_sync_no_records(self):
        """测试无记录时返回 0"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.load = MagicMock()
                enricher.records = []
                enricher.enrich = AsyncMock()
                enricher.close = MagicMock()

                result = enricher.run()

        self.assertEqual(result, 0)
        enricher.enrich.assert_not_awaited()
        enricher.close.assert_called_once()

    def test_run_sync_always_close(self):
        """测试无论成功或异常都会调用 close"""
        with self._patch_cdn_load():
            with patch("modules.enrich.Database"):
                enricher = self.EnrichClass("/tmp/test.db")
                enricher.load = MagicMock(side_effect=Exception("DB Error"))
                enricher.close = MagicMock()

                with self.assertRaises(Exception):
                    enricher.run()

                enricher.close.assert_called_once()

    # ==================================================================
    # 9. 模块级 run() 函数
    # ==================================================================

    def test_module_run(self):
        """测试模块级 run() 函数"""
        with patch("modules.enrich.Enrich") as MockEnrich:
            mock_instance = MagicMock()
            mock_instance.run.return_value = 10
            MockEnrich.return_value = mock_instance

            result = self.module.run("/tmp/test.db", "example_com", concurrent=100)

        self.assertEqual(result, 10)
        MockEnrich.assert_called_once_with("/tmp/test.db", concurrent=100)
        mock_instance.run.assert_called_once_with("example_com")

    # ==================================================================
    # 10. ALIVE_CODES 常量验证
    # ==================================================================

    def test_alive_codes_contains_common_status(self):
        """测试 ALIVE_CODES 包含常见状态码"""
        self.assertIn(200, self.module.ALIVE_CODES)
        self.assertIn(301, self.module.ALIVE_CODES)
        self.assertIn(404, self.module.ALIVE_CODES)
        self.assertIn(500, self.module.ALIVE_CODES)

    def test_alive_codes_excludes_uncommon_status(self):
        """测试 ALIVE_CODES 排除了非常见状态码"""
        self.assertNotIn(100, self.module.ALIVE_CODES)
        self.assertNotIn(999, self.module.ALIVE_CODES)


class TestEnrichEdgeCases(unittest.TestCase):
    """边界情况和异常处理测试"""

    @classmethod
    def setUpClass(cls):
        import modules.enrich as enrich_module
        cls.module = enrich_module
        cls.EnrichClass = enrich_module.Enrich

    def _patch_cdn_load(self):
        return patch("modules.enrich.Path.exists", return_value=False)

    def test_enrich_dns_empty_subdomain(self):
        """测试空子域名跳过 DNS"""
        async def _test():
            mock_db = MagicMock()

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    with patch("modules.enrich.logger"):
                        enricher = self.EnrichClass("/tmp/test.db")
                        enricher.table_name = "test_com"
                        enricher.records = [
                            {"id": 1, "subdomain": "", "ip": ""},
                        ]

                        with patch("modules.enrich.dns_resolve.resolve_domain") as mock_dns:
                            with patch("modules.enrich.IPAsnInfo") as MockAsn:
                                mock_asn_instance = MagicMock()
                                mock_asn_instance.find.return_value = None
                                MockAsn.return_value = mock_asn_instance

                                result = await enricher.enrich(show_progress=False)
                                mock_dns.assert_not_called()

            self.assertEqual(result, 0)

        asyncio.run(_test())

    def test_enrich_http_empty_subdomain(self):
        """测试空子域名跳过 HTTP"""
        async def _test():
            mock_db = MagicMock()

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    with patch("modules.enrich.logger"):
                        enricher = self.EnrichClass("/tmp/test.db")
                        enricher.table_name = "test_com"
                        enricher.records = [
                            {"id": 1, "subdomain": "", "ip": "1.2.3.4"},
                        ]

                        with patch.object(self.EnrichClass, "_http_probe") as mock_http:
                            with patch("modules.enrich.IPAsnInfo") as MockAsn:
                                mock_asn_instance = MagicMock()
                                mock_asn_instance.find.return_value = None
                                MockAsn.return_value = mock_asn_instance

                                result = await enricher.enrich(show_progress=False)
                                mock_http.assert_not_called()

            self.assertEqual(result, 0)

        asyncio.run(_test())

    def test_enrich_ip_empty_first_ip(self):
        """测试第一个 IP 为空字符串时跳过"""
        async def _test():
            mock_db = MagicMock()

            with self._patch_cdn_load():
                with patch("modules.enrich.Database", return_value=mock_db):
                    with patch("modules.enrich.logger"):
                        enricher = self.EnrichClass("/tmp/test.db")
                        enricher.table_name = "test_com"
                        enricher.records = [
                            {"id": 1, "subdomain": "test.com", "ip": ",5.6.7.8"},
                        ]

                        with patch("modules.enrich.IPAsnInfo") as MockAsn:
                            mock_asn_instance = MagicMock()
                            MockAsn.return_value = mock_asn_instance

                            result = await enricher.enrich(show_progress=False)
                            mock_asn_instance.find.assert_not_called()

            self.assertEqual(result, 0)

        asyncio.run(_test())

    def test_update_record_special_chars_in_value(self):
        """测试更新值包含特殊字符"""
        mock_result = MagicMock()
        mock_result.success = True

        mock_db = MagicMock()
        mock_db.query.return_value = mock_result

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                with patch("modules.enrich.logger"):
                    enricher = self.EnrichClass("/tmp/test.db")
                    enricher.table_name = "test_com"

                    data = {
                        "title": "<script>alert(1)</script>",
                        "header": "{\"X-Test\": \"value\"}",
                        "org": "O\"Reilly"
                    }
                    ok = enricher._update_record(1, data)

        self.assertTrue(ok)
        call_args = mock_db.query.call_args[0]
        self.assertIn("title", call_args[0])
        self.assertIn("header", call_args[0])

    def test_concurrent_param_passed_to_executor(self):
        """测试并发参数正确传递给线程池"""
        import concurrent.futures

        mock_db = MagicMock()
        mock_db.query.return_value = MagicMock(success=True)

        with self._patch_cdn_load():
            with patch("modules.enrich.Database", return_value=mock_db):
                with patch("modules.enrich.logger"):
                    # 使用真实的 ThreadPoolExecutor，但 patch 其 submit 方法以返回真实 Future
                    real_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

                    with patch("concurrent.futures.ThreadPoolExecutor") as MockExecutor:
                        MockExecutor.return_value = real_executor

                        enricher = self.EnrichClass("/tmp/test.db", concurrent=50)
                        enricher.table_name = "test_com"
                        enricher.records = [
                            {"id": 1, "subdomain": "a.test.com", "ip": ""},
                        ]

                        async def _run():
                            with patch("modules.enrich.dns_resolve.resolve_domain", return_value=None):
                                await enricher.enrich(show_progress=False)

                        asyncio.run(_run())

                        MockExecutor.assert_called_once_with(max_workers=50)

                    real_executor.shutdown(wait=False)


if __name__ == "__main__":
    unittest.main()
