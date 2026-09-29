# 子域名接管检测模块 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `python justone.py takeover example.com` 子域名接管检测功能

**Architecture:** DNS CNAME 查询 → 指纹匹配 → HTTP 确认的双阶段检测。fingerprints.py 负责指纹加载和匹配逻辑，takeover.py 负责编排检测流程。TakeoverResult dataclass 统一输出。

**Tech Stack:** dnspython, aiohttp, asyncio, json, re, functools.lru_cache

---

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `data/takeover_fingerprints.json` | 创建 | 指纹数据（15 个服务） |
| `modules/takeover/__init__.py` | 创建 | 导出 TakeoverCheck, TakeoverResult, takeover_run |
| `modules/takeover/fingerprints.py` | 创建 | 指纹加载 + CNAME/HTTP 指纹匹配工具函数 |
| `modules/takeover/takeover.py` | 创建 | TakeoverCheck 主类 + TakeoverResult dataclass |
| `tests/test_takeover.py` | 创建 | 全量测试 |
| `justone.py` | 修改 | 新增 takeover CLI 子命令 |
| `config/settings.py` | 修改 | takeover_concurrent 字段 |

---

### Task 1: 指纹数据文件

**Files:**
- Create: `data/takeover_fingerprints.json`

- [ ] **Step 1: 创建指纹 JSON 文件**

```json
{
  "aws-s3": {
    "name": "AWS S3",
    "severity": "high",
    "cname_match": "regex",
    "cname": ["\\.s3\\.amazonaws\\.com$", "\\.s3-website[-\\.]"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "NoSuchBucket", "required": true},
        {"type": "header", "pattern": "x-amz-request-id", "required": false}
      ],
      "status_codes": [404, 403]
    }
  },
  "github-pages": {
    "name": "GitHub Pages",
    "severity": "high",
    "cname_match": "suffix",
    "cname": [".github.io"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "There isn't a GitHub Pages site here", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "heroku": {
    "name": "Heroku",
    "severity": "high",
    "cname_match": "regex",
    "cname": ["\\.herokudns\\.com$", "\\.herokussl\\.com$", "\\.herokuapp\\.com$"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "No such app", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "azure-cloudapp": {
    "name": "Azure CloudApp",
    "severity": "high",
    "cname_match": "suffix",
    "cname": [".cloudapp.net"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "was not found", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "firebase": {
    "name": "Firebase",
    "severity": "high",
    "cname_match": "suffix",
    "cname": [".firebaseapp.com", ".web.app"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "Firebase Hosting Site Not Found", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "digitalocean-spaces": {
    "name": "DigitalOcean Spaces",
    "severity": "medium",
    "cname_match": "regex",
    "cname": ["\\.digitaloceanspaces\\.com$", "\\.fra1\\.digitaloceanspaces\\.com$"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "NoSuchBucket", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "shopify": {
    "name": "Shopify",
    "severity": "high",
    "cname_match": "suffix",
    "cname": [".myshopify.com", ".shopify.com"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "Sorry, this shop is currently unavailable", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "wordpress-com": {
    "name": "WordPress.com",
    "severity": "high",
    "cname_match": "suffix",
    "cname": [".wordpress.com"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "Do you want to register", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "pantheon": {
    "name": "Pantheon",
    "severity": "high",
    "cname_match": "suffix",
    "cname": [".pantheonsite.io", ".pantheon.io"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "The gods are angry", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "readme-io": {
    "name": "Readme.io",
    "severity": "medium",
    "cname_match": "suffix",
    "cname": [".readme.io"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "Project doesn't exist", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "surge-sh": {
    "name": "Surge.sh",
    "severity": "medium",
    "cname_match": "suffix",
    "cname": [".surge.sh"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "project not found", "required": true}
      ],
      "status_codes": [404, 403]
    }
  },
  "bitbucket": {
    "name": "Bitbucket",
    "severity": "high",
    "cname_match": "suffix",
    "cname": [".bitbucket.io"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "Repository not found", "required": true}
      ],
      "status_codes": [404]
    }
  },
  "zendesk": {
    "name": "Zendesk",
    "severity": "medium",
    "cname_match": "suffix",
    "cname": [".zendesk.com"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "Help Center Closed", "required": true}
      ],
      "status_codes": [404, 200]
    }
  },
  "atlassian": {
    "name": "Atlassian",
    "severity": "high",
    "cname_match": "suffix",
    "cname": [".atlassian.net"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "This site can't be reached", "required": false},
        {"type": "body", "pattern": "The site you are looking for does not exist", "required": false}
      ],
      "status_codes": [404, 502, 503]
    }
  },
  "cargo-collective": {
    "name": "Cargo Collective",
    "severity": "medium",
    "cname_match": "suffix",
    "cname": [".cargocollective.com"],
    "ns_takeover": false,
    "http_check": {
      "enabled": true,
      "method": "GET",
      "paths": ["/"],
      "fingerprints": [
        {"type": "body", "pattern": "The site you were looking for doesn't exist", "required": true}
      ],
      "status_codes": [404]
    }
  }
}
```

- [ ] **Step 2: 验证 JSON 格式有效性**

Run: `python -c "import json; json.load(open('data/takeover_fingerprints.json', 'r', encoding='utf-8')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add data/takeover_fingerprints.json
git commit -m "feat(takeover): add fingerprint data for 15 services"
```

---

### Task 2: fingerprints.py — 指纹工具模块

**Files:**
- Create: `modules/takeover/fingerprints.py`
- Create: `modules/takeover/__init__.py`
- Test: `tests/test_takeover.py`（本任务中的测试部分）

- [ ] **Step 1: 创建 tests/test_takeover.py 并写入指纹加载测试**

```python
# -*- coding: utf-8 -*-
"""
子域名接管检测模块测试
"""

import json
import re
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
        # 构造一个 contains 类型的指纹
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


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: 运行测试 — 预期失败**

Run: `pytest tests/test_takeover.py::TestFingerprints -v 2>&1`
Expected: ModuleNotFoundError / ImportError

- [ ] **Step 3: 创建 modules/takeover/fingerprints.py**

```python
# -*- coding: utf-8 -*-
"""
指纹加载和匹配模块

提供指纹文件的加载、缓存、热重载以及 CNAME 模式匹配功能。
"""

import json
import re
from pathlib import Path
from typing import Optional, Any


def load_fingerprints(path: Optional[Path] = None, reload: bool = False) -> dict:
    """
    加载指纹文件

    :param path: 指纹文件路径，默认为 data/takeover_fingerprints.json
    :param reload: 是否强制重新加载（不使用缓存）
    :return: 服务指纹字典 {service_id: fingerprint}
    """
    if path is None:
        path = Path(__file__).parent.parent.parent / 'data' / 'takeover_fingerprints.json'

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def match_cname(cname: str, fingerprint: dict) -> Optional[str]:
    """
    检查 CNAME 是否匹配指纹的 cname 模式

    :param cname: CNAME 目标
    :param fingerprint: 单条指纹字典
    :return: 匹配到的模式字符串，不匹配返回 None
    """
    match_type = fingerprint.get('cname_match', 'contains')
    patterns = fingerprint.get('cname', [])

    if match_type == 'suffix':
        for p in patterns:
            if cname.endswith(p):
                return p
    elif match_type == 'regex':
        for p in patterns:
            if re.search(p, cname):
                return p
    elif match_type == 'contains':
        for p in patterns:
            if p in cname:
                return p
    return None


def find_matching_fingerprint(cname: str, fingerprints: dict) -> Optional[tuple]:
    """
    在所有指纹中查找匹配的条目

    :param cname: CNAME 目标
    :param fingerprints: 指纹字典
    :return: (service_id, fingerprint_dict, matched_pattern) 或 None
    """
    for service_id, fp in fingerprints.items():
        matched = match_cname(cname, fp)
        if matched:
            return (service_id, fp, matched)
    return None
```

- [ ] **Step 4: 创建 modules/takeover/__init__.py**

```python
# -*- coding: utf-8 -*-
"""
子域名接管检测模块
"""

from .fingerprints import load_fingerprints, match_cname, find_matching_fingerprint
from .takeover import TakeoverCheck, TakeoverResult, takeover_run

__all__ = [
    'load_fingerprints', 'match_cname', 'find_matching_fingerprint',
    'TakeoverCheck', 'TakeoverResult', 'takeover_run',
]
```

- [ ] **Step 5: 运行测试 — 预期通过**

Run: `pytest tests/test_takeover.py::TestFingerprints -v 2>&1`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add modules/takeover/ modules/takeover/fingerprints.py
git commit -m "feat(takeover): add fingerprint loading and CNAME matching"
```

---

### Task 3: TakeoverCheck + TakeoverResult

**Files:**
- Create: `modules/takeover/takeover.py`
- Modify: `tests/test_takeover.py`（追加测试）

- [ ] **Step 1: 追加 TakeoverResult 和 DNS 解析测试**

追加到 `tests/test_takeover.py`：

```python
from unittest.mock import patch, MagicMock
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

    @patch('dns.resolver.resolve')
    def test_resolve_cname_success(self, mock_resolve):
        mock_answer = MagicMock()
        mock_answer.target = 'test.github.io.'
        mock_resolve.return_value = [mock_answer]

        check = TakeoverCheck('example.com')
        cname, status = check._resolve_cname('test.example.com')
        self.assertEqual(cname, 'test.github.io.')
        self.assertEqual(status, 'NOERROR')

    @patch('dns.resolver.resolve')
    def test_resolve_cname_nxdomain(self, mock_resolve):
        import dns.resolver
        mock_resolve.side_effect = dns.resolver.NXDOMAIN

        check = TakeoverCheck('example.com')
        cname, status = check._resolve_cname('nonexistent.example.com')
        self.assertIsNone(cname)
        self.assertEqual(status, 'NXDOMAIN')

    @patch('dns.resolver.resolve')
    def test_resolve_cname_noanswer(self, mock_resolve):
        import dns.resolver
        mock_resolve.side_effect = dns.resolver.NoAnswer

        check = TakeoverCheck('example.com')
        cname, status = check._resolve_cname('test.example.com')
        self.assertIsNone(cname)
        self.assertEqual(status, 'NOERROR')
```

- [ ] **Step 2: 运行测试 — 预期失败**

Run: `pytest tests/test_takeover.py::TestTakeoverResult tests/test_takeover.py::TestTakeoverDNS -v 2>&1`
Expected: ImportError (takeover.py 不存在) 或部分失败

- [ ] **Step 3: 创建 modules/takeover/takeover.py**

```python
# -*- coding: utf-8 -*-
"""
子域名接管检测主模块

负责 DNS CNAME 查询、指纹匹配和 HTTP 确认的编排。
"""

import asyncio
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, Set, List, Tuple, Dict, Any

import aiohttp
import dns.resolver

from modules.takeover.fingerprints import load_fingerprints, find_matching_fingerprint


@dataclass
class TakeoverResult:
    """单个子域名的接管检测结果"""
    subdomain: str
    cname: Optional[str] = None
    service: Optional[str] = None
    severity: Optional[str] = None
    status: str = 'not_vulnerable'
    detail: dict = field(default_factory=dict)


RISK_ORDER = {'vulnerable': 0, 'likely': 1, 'not_vulnerable': 2, 'unknown': 3, 'error': 4}


class TakeoverCheck:
    """
    子域名接管检测器

    通过 DNS CNAME 查询 + HTTP 响应指纹双重确认来判定接管风险。
    """

    def __init__(self, domain: str, config: Optional[dict] = None):
        """
        :param domain: 目标域名
        :param config: 可选配置（fingerprint_file, concurrent, http_timeout）
        """
        self.domain = domain
        self.config = config or {}
        self.fingerprints = load_fingerprints(
            self.config.get('fingerprint_file')
        )
        self.concurrent = self.config.get('concurrent', 20)
        self.http_timeout = self.config.get('http_timeout', 10)

    @lru_cache(maxsize=1024)
    def _resolve_cname(self, subdomain: str) -> Tuple[Optional[str], str]:
        """
        同步 DNS CNAME 查询（带 lru_cache）

        :param subdomain: 子域名
        :return: (cname_target, dns_status)
                 dns_status: NOERROR / NXDOMAIN / TIMEOUT / ERROR:msg
        """
        try:
            answers = dns.resolver.resolve(subdomain, 'CNAME')
            return (str(answers[0].target), 'NOERROR')
        except dns.resolver.NoAnswer:
            return (None, 'NOERROR')
        except dns.resolver.NXDOMAIN:
            return (None, 'NXDOMAIN')
        except dns.resolver.Timeout:
            return (None, 'TIMEOUT')
        except Exception as e:
            return (None, f'ERROR:{e}')

    async def _check_http_path(
        self, session: aiohttp.ClientSession, subdomain: str, path: str,
        fp: dict
    ) -> dict:
        """
        检查单一路径的 HTTP 响应

        :return: {status_code, body, headers, error}
        """
        url = f'https://{subdomain}{path}'
        try:
            async with session.get(
                url,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=self.http_timeout),
                allow_redirects=True,
                max_redirects=5,
            ) as resp:
                body = await resp.text()
                return {
                    'status_code': resp.status,
                    'body': body,
                    'headers': dict(resp.headers),
                    'error': None,
                }
        except asyncio.TimeoutError:
            return {'status_code': 0, 'body': '', 'headers': {}, 'error': 'timeout'}
        except Exception as e:
            return {'status_code': 0, 'body': '', 'headers': {}, 'error': str(e)}

    def _check_fingerprint_match(self, http_check: dict, resp: dict) -> Tuple[bool, List[str], List[str]]:
        """
        检查 HTTP 响应是否匹配指纹

        :param http_check: 指纹中的 http_check 配置
        :param resp: _check_http_path 的返回
        :return: (status_match, matched_fingerprints, missed_fingerprints)
        """
        expected_codes = http_check.get('status_codes', [200])
        status_match = resp['status_code'] in expected_codes

        if not status_match:
            return (False, [], [])

        fingerprints = http_check.get('fingerprints', [])
        matched = []
        missed = []

        for f in fingerprints:
            pattern = f['pattern']
            if f['type'] == 'body':
                if pattern in resp['body']:
                    matched.append(pattern)
                else:
                    missed.append(pattern)
            elif f['type'] == 'header':
                header_val = next(
                    (v for k, v in resp['headers'].items() if k.lower() == pattern.lower()),
                    None
                )
                if header_val:
                    matched.append(pattern)
                else:
                    missed.append(pattern)

        return (True, matched, missed)

    def _judge(self, fp: dict, status_match: bool, matched: List[str],
               missed: List[str]) -> str:
        """
        判定风险等级

        :return: vulnerable / likely / not_vulnerable
        """
        if not status_match:
            return 'not_vulnerable'

        fingerprints = fp.get('http_check', {}).get('fingerprints', [])
        required = [f for f in fingerprints if f.get('required', False)]

        if required:
            required_matched = all(p in matched for f in required for p in ([f['pattern']]))
            # 更精确的 required 判断
            required_patterns = {f['pattern'] for f in required}
            if required_patterns and required_patterns.issubset(set(matched)):
                return 'vulnerable'
            return 'likely'

        # 无 required 字段：有任意匹配就算 likely
        if matched:
            return 'likely'
        return 'likely'

    async def _check_http(self, subdomain: str, fp: dict) -> dict:
        """
        对所有 paths 并行 HTTP 检查，取最高风险

        :return: {status_code, body, matched_fingerprints, ...}
        """
        http_check = fp.get('http_check', {})
        if not http_check.get('enabled', True):
            return {'http_enabled': False}

        paths = http_check.get('paths', ['/'])

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._check_http_path(session, subdomain, p, fp) for p in paths]
            responses = await asyncio.gather(*tasks)

        best = None
        best_risk = 99
        for resp in responses:
            if resp.get('error'):
                continue
            status_match, matched, missed = self._check_fingerprint_match(http_check, resp)
            status = self._judge(fp, status_match, matched, missed)
            risk = RISK_ORDER.get(status, 99)
            if risk < best_risk:
                best_risk = risk
                best = {
                    'http_enabled': True,
                    'http_path': paths[responses.index(resp)],
                    'http_status': resp['status_code'],
                    'matched_fingerprints': matched,
                    'missed_fingerprints': missed,
                    'judgment': status,
                    'http_error': None,
                }

        if best is None:
            # 所有路径都出错
            first_error = responses[0].get('error', 'unknown') if responses else 'unknown'
            return {
                'http_enabled': True,
                'http_path': paths[0],
                'http_status': 0,
                'matched_fingerprints': [],
                'missed_fingerprints': [],
                'judgment': 'unknown',
                'http_error': first_error,
            }

        return best

    def check_subdomain(self, subdomain: str) -> TakeoverResult:
        """
        检查单个子域名的接管风险（同步入口）

        :param subdomain: 要检查的子域名
        :return: TakeoverResult
        """
        cname, dns_status = self._resolve_cname(subdomain)

        # DNS 异常处理
        if dns_status in ('TIMEOUT',) or dns_status.startswith('ERROR:'):
            return TakeoverResult(
                subdomain=subdomain,
                cname=cname,
                status='error',
                detail={'dns_status': dns_status, 'cname_matched': None}
            )

        if cname is None:
            return TakeoverResult(
                subdomain=subdomain,
                cname=None,
                status='not_vulnerable',
                detail={'dns_status': dns_status, 'cname_matched': None}
            )

        # CNAME 匹配
        match_result = find_matching_fingerprint(cname, self.fingerprints)
        if match_result is None:
            return TakeoverResult(
                subdomain=subdomain,
                cname=cname,
                status='not_vulnerable',
                detail={'dns_status': dns_status, 'cname_matched': None}
            )

        service_id, fp, matched_pattern = match_result
        result = TakeoverResult(
            subdomain=subdomain,
            cname=cname,
            service=service_id,
            severity=fp.get('severity'),
            detail={
                'dns_status': dns_status,
                'cname_matched': matched_pattern,
            }
        )

        # HTTP 确认阶段 — 需要事件循环
        http_check = fp.get('http_check', {})
        if http_check.get('enabled', True):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            http_result = loop.run_until_complete(self._check_http(subdomain, fp))
            result.detail.update(http_result)
            result.status = http_result.get('judgment', 'unknown')
        else:
            result.status = 'likely'

        return result

    async def run(self, subdomains: Set[str]) -> List[TakeoverResult]:
        """
        批量异步检查子域名

        :param subdomains: 子域名集合
        :return: TakeoverResult 列表
        """
        semaphore = asyncio.Semaphore(self.concurrent)

        async def _check_one(subdomain: str) -> TakeoverResult:
            async with semaphore:
                cname, dns_status = self._resolve_cname(subdomain)

                if dns_status in ('TIMEOUT',) or dns_status.startswith('ERROR:'):
                    return TakeoverResult(
                        subdomain=subdomain, cname=cname, status='error',
                        detail={'dns_status': dns_status, 'cname_matched': None}
                    )
                if cname is None:
                    return TakeoverResult(
                        subdomain=subdomain, cname=None, status='not_vulnerable',
                        detail={'dns_status': dns_status, 'cname_matched': None}
                    )

                match_result = find_matching_fingerprint(cname, self.fingerprints)
                if match_result is None:
                    return TakeoverResult(
                        subdomain=subdomain, cname=cname, status='not_vulnerable',
                        detail={'dns_status': dns_status, 'cname_matched': None}
                    )

                service_id, fp, matched_pattern = match_result
                result = TakeoverResult(
                    subdomain=subdomain, cname=cname, service=service_id,
                    severity=fp.get('severity'),
                    detail={'dns_status': dns_status, 'cname_matched': matched_pattern}
                )

                http_check = fp.get('http_check', {})
                if http_check.get('enabled', True):
                    http_result = await self._check_http(subdomain, fp)
                    result.detail.update(http_result)
                    result.status = http_result.get('judgment', 'unknown')
                else:
                    result.status = 'likely'

                return result

        tasks = [_check_one(s) for s in subdomains]
        return list(await asyncio.gather(*tasks))


def takeover_run(domain: str, subdomains: Set[str],
                 config: Optional[dict] = None) -> List[dict]:
    """
    模块级入口（同步）

    :param domain: 目标域名
    :param subdomains: 子域名集合
    :param config: 可选配置
    :return: 字典列表（每个子域名的检测结果）
    """
    check = TakeoverCheck(domain, config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(check.run(subdomains))
        return [{
            'subdomain': r.subdomain,
            'cname': r.cname,
            'service': r.service,
            'severity': r.severity,
            'status': r.status,
            'detail': r.detail,
        } for r in results]
    finally:
        loop.close()
```

- [ ] **Step 4: 运行测试 — 预期通过**

Run: `pytest tests/test_takeover.py::TestTakeoverResult tests/test_takeover.py::TestTakeoverDNS -v 2>&1`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add modules/takeover/takeover.py
git commit -m "feat(takeover): add TakeoverCheck with DNS resolution and CNAME matching"
```

---

### Task 4: HTTP 确认 + 全链路编排测试

**Files:**
- Modify: `tests/test_takeover.py`（追加 HTTP 和全链路测试）

- [ ] **Step 1: 追加 HTTP 指纹匹配和全链路测试**

追加到 `tests/test_takeover.py`：

```python
class TestTakeoverHTTP(unittest.TestCase):
    """HTTP 指纹检查测试"""

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

    def test_judge_likely_no_required(self):
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


class TestTakeoverIntegration(unittest.TestCase):
    """全链路 mock 集成测试"""

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    def test_check_subdomain_no_cname(self, mock_resolve):
        mock_resolve.return_value = (None, 'NOERROR')
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'not_vulnerable')
        self.assertIsNone(result.cname)

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    def test_check_subdomain_cname_no_match(self, mock_resolve):
        mock_resolve.return_value = ('test.unknown-service.com.', 'NOERROR')
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'not_vulnerable')
        self.assertEqual(result.cname, 'test.unknown-service.com.')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    def test_check_subdomain_nxdomain(self, mock_resolve):
        mock_resolve.return_value = (None, 'NXDOMAIN')
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'not_vulnerable')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    def test_check_subdomain_timeout(self, mock_resolve):
        mock_resolve.return_value = (None, 'TIMEOUT')
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'error')

    @patch('modules.takeover.takeover.TakeoverCheck._resolve_cname')
    @patch('modules.takeover.takeover.TakeoverCheck._check_http')
    def test_check_subdomain_vulnerable(self, mock_http, mock_resolve):
        mock_resolve.return_value = ('test.github.io.', 'NOERROR')
        mock_http.return_value = {
            'http_enabled': True, 'http_path': '/', 'http_status': 404,
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
    def test_check_subdomain_likely(self, mock_http, mock_resolve):
        mock_resolve.return_value = ('test.github.io.', 'NOERROR')
        mock_http.return_value = {
            'http_enabled': True, 'http_path': '/', 'http_status': 404,
            'matched_fingerprints': [],
            'missed_fingerprints': ["There isn't a GitHub Pages site here"],
            'judgment': 'likely', 'http_error': None,
        }
        check = TakeoverCheck('example.com')
        result = check.check_subdomain('test.example.com')
        self.assertEqual(result.status, 'likely')
        self.assertEqual(result.service, 'github-pages')

    @patch('modules.takeover.takeover.takeover_run')
    def test_takeover_run_returns_list_of_dicts(self, mock_run):
        mock_run.return_value = [
            {'subdomain': 'test.example.com', 'cname': 'test.github.io.',
             'service': 'github-pages', 'severity': 'high',
             'status': 'vulnerable', 'detail': {}}
        ]
        from modules.takeover import takeover_run
        results = takeover_run('example.com', {'test.example.com'})
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertIn('status', results[0])
```

- [ ] **Step 2: 运行测试 — 预期通过**

Run: `pytest tests/test_takeover.py -v 2>&1`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_takeover.py
git commit -m "feat(takeover): add HTTP fingerprint matching and integration tests"
```

---

### Task 5: CLI + Settings 集成

**Files:**
- Modify: `justone.py`
- Modify: `config/settings.py`

- [ ] **Step 1: 修改 config/settings.py**

找到 `takeover_enable` 字段位置，在其后追加：

```python
    # 子域名接管检测并发数
    takeover_concurrent: int = 20
```

- [ ] **Step 2: 在 justone.py 末尾（brute 命令之后）添加 takeover 子命令**

```python
@app.command()
def takeover(
    target: Optional[str] = typer.Argument(None, help="目标域名"),
    input_file: Optional[Path] = typer.Option(None, "--input", "-i", help="子域名列表文件（每行一个）"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径"),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式: csv/json/txt"),
    concurrent: int = typer.Option(20, "--concurrent", "-c", help="并发数"),
    fingerprint_file: Optional[Path] = typer.Option(None, "--fingerprint-file", help="自定义指纹文件路径"),
):
    """
    检测子域名接管风险

    通过 DNS CNAME + HTTP 响应指纹双重确认判断子域名是否可被接管。

    示例:
        python justone.py takeover example.com
        python justone.py takeover -i subdomains.txt
        python justone.py takeover example.com --concurrent 50
    """
    from modules.takeover import takeover_run

    init_logging()

    subdomains: Set[str] = set()

    if input_file:
        if not input_file.exists():
            console.print(f"[bold red]错误: 文件不存在: {input_file}[/bold red]")
            raise typer.Exit(1)
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    subdomains.add(line)
        console.print(f"[bold cyan]从文件加载 {len(subdomains)} 个子域名[/bold cyan]")
    elif target:
        domain_obj = Domain(target)
        main_domain = domain_obj.registered()
        console.print(f"[bold cyan]检测子域名接管: {main_domain}[/bold cyan]")

        # 先收集子域名
        console.print("[cyan]执行信息收集...[/cyan]")
        collect = Collect(main_domain)
        collected = set(collect.run())
        console.print(f"[dim]收集到 {len(collected)} 个子域名[/dim]")

        # 再加爆破
        brute_module = Brute(main_domain)
        brute_subdomains = brute_module.run()
        console.print(f"[dim]爆破发现 {len(brute_subdomains)} 个[/dim]")

        subdomains = collected | brute_subdomains
    else:
        console.print("[bold red]错误: 请指定目标域名或使用 -i 指定输入文件[/bold red]")
        raise typer.Exit(1)

    if not subdomains:
        console.print("[yellow]没有子域名需要检测[/yellow]")
        return

    console.print(f"[cyan]开始检测 {len(subdomains)} 个子域名的接管风险...[/cyan]")

    config = {
        'concurrent': concurrent,
    }
    if fingerprint_file:
        config['fingerprint_file'] = fingerprint_file

    results = takeover_run(main_domain if target else 'unknown', subdomains, config)

    # 统计
    vulnerable = [r for r in results if r['status'] == 'vulnerable']
    likely = [r for r in results if r['status'] == 'likely']
    errors = [r for r in results if r['status'] == 'error']

    console.print(f"\n[bold]检测完成:[/bold]")
    console.print(f"  [bold red]可接管: {len(vulnerable)}[/bold red]")
    console.print(f"  [bold yellow]可疑: {len(likely)}[/bold yellow]")
    console.print(f"  [dim]安全: {len(results) - len(vulnerable) - len(likely) - len(errors)}[/dim]")
    console.print(f"  [dim]错误: {len(errors)}[/dim]")

    if vulnerable:
        console.print(f"\n[bold red]!!! 可接管域名 !!![/bold red]")
        for r in vulnerable:
            console.print(f"  [red]{r['subdomain']}[/red] → {r['cname']} ({r['service']})")

    if likely:
        console.print(f"\n[bold yellow]可疑域名:[/bold yellow]")
        for r in likely:
            console.print(f"  [yellow]{r['subdomain']}[/yellow] → {r['cname']} ({r['service']})")

    if results:
        if not output:
            if target:
                output = get_default_output(main_domain, 'takeover', format)
            else:
                output = get_default_output('result', 'takeover', format)
        if format == 'txt':
            export_subdomains(
                [f"{r['subdomain']} {r['status']} {r.get('service', '')} {r.get('cname', '')}"
                 for r in results],
                output, 'txt'
            )
        else:
            export_results(results, output, format)
        console.print(f"[green]结果已保存到: {output}[/green]")
```

同时需要在 justone.py 顶部 import 处追加：
```python
import asyncio
from modules.takeover import takeover_run
```

实际 asyncio 已 import，只需在合适位置追加 takeover_run import。

- [ ] **Step 3: 验证 CLI 帮助输出**

Run: `python justone.py takeover --help 2>&1`
Expected: 显示 takeover 命令帮助信息，包含 target, --input, --output, --format, --concurrent, --fingerprint-file

- [ ] **Step 4: Commit**

```bash
git add justone.py config/settings.py
git commit -m "feat(takeover): add takeover CLI command and settings"
```

---

### Task 6: 运行全量测试验证无回归

- [ ] **Step 1: 运行全部测试**

Run: `pytest -v 2>&1`
Expected: 271 passed, 7 skipped（新增 1 个测试文件）

- [ ] **Step 2: 最终提交**

```bash
git add -A
git commit -m "feat(takeover): complete subdomain takeover detection module"
```

---

## Spec 覆盖检查

| Spec 需求 | 对应 Task |
|-----------|-----------|
| 指纹数据文件 (15 服务) | Task 1 |
| 指纹加载 + 热重载 | Task 2 |
| CNAME 匹配 (suffix/regex/contains) | Task 2 |
| TakeoverResult dataclass | Task 3 |
| DNS 异常细分 (NXDOMAIN → not_vulnerable) | Task 3 |
| HTTP 指纹确认 (paths 并行取最高风险) | Task 4 |
| 判定算法 (required/optional) | Task 4 |
| `@lru_cache` DNS 缓存 | Task 3 |
| CLI 子命令 takeover | Task 5 |
| settings.py 集成 | Task 5 |
| detail 结构化输出 | Task 3, 4 |
| 测试全链路 mock | Task 2, 3, 4 |
