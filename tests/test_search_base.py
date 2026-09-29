"""
Unit tests for common/search.py（搜索引擎基类）
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from common.search import Search


def _mock_response():
    """构造可通过 Module.get 的最小响应对象"""
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b'ok'
    return resp


class TestSearchThrottle(unittest.TestCase):
    """测试搜索引擎基类的请求节流"""

    def _patched_request(self, instance):
        """patch 掉底层 HTTP 请求，仅验证节流行为"""
        return patch.object(
            instance, '_do_request', return_value=_mock_response()
        )

    def test_first_request_not_delayed(self):
        """首次请求不应等待"""
        s = Search('example.com')
        s.delay = 0.3
        start = time.time()
        with self._patched_request(s):
            s.get('http://example.com', check=False)
        self.assertLess(time.time() - start, 0.2)

    def test_consecutive_requests_throttled(self):
        """连续请求间隔小于 delay 时应被节流"""
        s = Search('example.com')
        s.delay = 0.3
        start = time.time()
        with self._patched_request(s):
            s.get('http://example.com', check=False)
            s.get('http://example.com', check=False)
        elapsed = time.time() - start
        # 第二次请求应至少补足 delay 间隔
        self.assertGreaterEqual(elapsed, 0.29)

    def test_delay_zero_no_throttle(self):
        """delay=0 时不节流"""
        s = Search('example.com')
        s.delay = 0
        start = time.time()
        with self._patched_request(s):
            for _ in range(3):
                s.get('http://example.com', check=False)
        self.assertLess(time.time() - start, 0.2)

    def test_post_also_throttled(self):
        """POST 请求同样受节流约束"""
        s = Search('example.com')
        s.delay = 0.3
        start = time.time()
        with self._patched_request(s):
            s.post('http://example.com', check=False)
            s.post('http://example.com', check=False)
        self.assertGreaterEqual(time.time() - start, 0.29)

    def test_delay_from_config(self):
        """search_delay 配置项可覆盖默认间隔"""
        s = Search('example.com', {'search_delay': 2.5})
        self.assertEqual(s.delay, 2.5)

    def test_default_delay(self):
        """默认请求间隔为 1 秒"""
        s = Search('example.com')
        self.assertEqual(s.delay, 1.0)


if __name__ == '__main__':
    unittest.main()
