# 子域名接管检测模块 — 设计文档

## 概述

实现子域名接管（Subdomain Takeover）检测功能，支持 DNS CNAME 指纹匹配 + HTTP 响应体双重确认，作为独立 CLI 子命令集成到 JustOne。

## 数据格式

### 指纹文件: `data/takeover_fingerprints.json`

```json
{
  "service_id": "aws-s3",
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
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `service_id` | str | 唯一标识 |
| `name` | str | 展示名称 |
| `severity` | str | high / medium / low |
| `cname_match` | str | `suffix` / `regex` / `contains` |
| `cname` | list[str] | 匹配模式列表 |
| `ns_takeover` | bool | 是否支持 NS 接管检测（预留，二期实现） |
| `http_check.enabled` | bool | 是否启用 HTTP 确认 |
| `http_check.method` | str | GET / HEAD |
| `http_check.paths` | list[str] | 请求路径列表（并行检查取最高风险） |
| `http_check.fingerprints` | list | 指纹定义（type: body/header, pattern, required）|
| `http_check.status_codes` | list[int] | 期望状态码 |

初始覆盖 15 个高频服务：AWS S3, GitHub Pages, Heroku, Azure CloudApp, Firebase, DigitalOcean Spaces, Shopify, WordPress.com, Pantheon, Readme.io, Surge.sh, Bitbucket, Zendesk, Atlassian, Cargo Collective。

### 指纹热加载

`fingerprints.py` 支持自定义路径和运行时重载：

```python
def load_fingerprints(path: Optional[Path] = None, reload: bool = False) -> dict:
    """加载指纹文件；reload=True 时丢弃缓存重新读取"""
```

## 判定等级

| 等级 | 条件 |
|------|------|
| `vulnerable` | CNAME 匹配 + 所有 required 指纹命中 + 状态码匹配 |
| `likely` | CNAME 匹配 + 无 required 指纹但可选指纹命中 / 或 required 部分命中 / 或仅状态码匹配 |
| `not_vulnerable` | CNAME 匹配但 HTTP 返回正常内容 |
| `unknown` | CNAME 匹配但 HTTP 超时/网络错误 |
| `error` | DNS 查询异常（SERVFAIL / 超时 / 网络不可达），注意 NXDOMAIN 不算 error |

### 判定算法（HTTP 指纹匹配）

```python
required = [f for f in fingerprints if f.get("required", False)]
optional = [f for f in fingerprints if not f.get("required", False)]

if status_code not in expected_codes:
    return NOT_VULNERABLE

if required:
    if all(r.matched for r in required):
        return VULNERABLE
    else:
        return LIKELY   # required 有未命中，但仍有可能
else:
    # 无 required 指纹：只要有可选指纹命中就算 LIKELY
    if any(o.matched for o in optional):
        return LIKELY
    else:
        return LIKELY   # 状态码匹配但无特定指纹也是 LIKELY（CNAME 已匹配）
```

## 检测流程

```
subdomain
  │
  ├─ DNS CNAME 查询
  │    ├─ NXDOMAIN → NOT_VULNERABLE (明确无记录，非 error)
  │    ├─ SERVFAIL/TIMEOUT/NET_UNREACHABLE → ERROR
  │    ├─ NOERROR 无 CNAME → NOT_VULNERABLE
  │    └─ 有 CNAME
  │         └─ 匹配指纹 cname 模式
  │              ├─ 不匹配 → NOT_VULNERABLE
  │              └─ 匹配 → HTTP 确认阶段
  │                   ├─ paths 并行检查，取最高风险
  │                   │    vulnerable > likely > not_vulnerable > unknown > error
  │                   ├─ 跟随重定向 ≤ 5 次，忽略 SSL 错误，超时 10s
  │                   └─ 按判定算法返回结果
```

## 数据结构

```python
@dataclass
class TakeoverResult:
    subdomain: str
    cname: Optional[str]          # CNAME 目标，nil 则无 CNAME
    service: Optional[str]        # 匹配到的服务标识，nil 则无匹配
    status: str                   # vulnerable / likely / not_vulnerable / unknown / error
    severity: Optional[str]       # high / medium / low，仅 status 含风险时有效
    detail: dict                  # 结构化详情（见下文）
```

### detail 结构化格式

```python
{
    "cname_matched": "\\.s3\\.amazonaws\\.com$",  # 匹配到的模式 ID
    "dns_status": "NOERROR",                       # NXDOMAIN / SERVFAIL / TIMEOUT / NOERROR
    "http_path": "/",                              # 触发判定的路径
    "http_status": 404,                            # HTTP 状态码
    "matched_fingerprints": ["NoSuchBucket"],       # 命中的指纹
    "missed_fingerprints": ["x-amz-request-id"],   # 未命中的指纹
    "error": None,                                 # 错误信息（如有）
}
```

CSV 输出时将 `detail` 序列化为 JSON 字符串的一列。

## 模块结构

```
modules/takeover/
├── __init__.py               # 导出 TakeoverCheck, TakeoverResult, takeover_run
├── takeover.py               # TakeoverCheck 主类
└── fingerprints.py           # 指纹加载 + CNAME/HTTP 匹配逻辑
```

### TakeoverCheck 类

```python
from functools import lru_cache
from typing import Optional

class TakeoverCheck:
    def __init__(self, domain: str, config: dict = None):
        self.fingerprints = load_fingerprints()
        self.concurrent = (config or {}).get('concurrent', 20)

    def check_subdomain(self, subdomain: str) -> TakeoverResult:
        """检查单个子域名"""

    async def run(self, subdomains: set[str]) -> list[TakeoverResult]:
        """批量异步检查（aiohttp + asyncio 并发）"""

    @lru_cache(maxsize=1024)
    def _resolve_cname(self, subdomain: str) -> Optional[str]:
        """同步 DNS CNAME 查询（lru_cache 缓存结果）"""
```

注：`_resolve_cname` 使用同步 dnspython 查询并通过 `lru_cache` 缓存，由 `check_subdomain` 包装调用。

## CLI 集成

```python
@app.command()
def takeover(
    target: Optional[str] = None,
    input_file: Optional[Path] = None,
    output: Optional[Path] = None,
    format: str = "csv",
    concurrent: int = 20,
    fingerprint_file: Optional[Path] = None,
):
    """检测子域名接管风险"""
```

与 `check` 命令模式一致，支持 `-i` 批量、`-o` 输出、`--fingerprint-file` 自定义指纹。

### settings.py 集成

已有字段 `takeover_enable: bool = False`，作为主控开关。新增 `takeover_concurrent: int = 20`。

## HTTP 检查策略

- 跟随重定向（最多 5 次）
- 忽略 SSL 证书错误（`verify=False`）
- 超时 10s
- 使用 `aiohttp` 并发请求
- `paths` 并行检查：对所有路径发起并发请求，取最高风险等级（vulnerable > likely > not_vulnerable > unknown > error）

## DNS 查询策略

- 使用 `dns.resolver.resolve(subdomain, 'CNAME')`（dnspython）
- 异常细分：
  - `NXDOMAIN` / `NoAnswer` → `dns_status: "NOERROR"`, 无 CNAME → `NOT_VULNERABLE`
  - `SERVFAIL` / `Timeout` / `NetworkError` → `dns_status: "ERROR"` → 返回 `ERROR`
- `@lru_cache` 缓存最多 1024 条 CNAME 查询结果

## 测试方案

| 测试 | 说明 |
|------|------|
| `test_load_fingerprints` | 验证 JSON 文件完整性和必填字段 |
| `test_cname_match` | suffix/regex/contains 各模式测试用例 |
| `test_http_fingerprint` | Mock aiohttp 响应，验证 body/header 检测算法 |
| `test_judgment` | 全链路 mock（DNS + HTTP），验证 5 种判定等级 + 细分条件 |
| `test_dns_error_handling` | NXDOMAIN / SERVFAIL / 超时 各自归到正确的等级 |
| `test_paths_parallel` | 多路径检查，验证取最高风险等级 |
| `test_cache` | 验证 `lru_cache` 对重复 CNAME 的命中 |
| `test_custom_fingerprint` | 自定义指纹文件加载 |

## 输出格式

### CSV

```csv
subdomain,cname,service,severity,status,detail
blog.example.com,blog.example.com.github.io,GitHub Pages,high,vulnerable,"{""dns_status"":""NOERROR"",""http_path"":""/"",""http_status"":404,""matched_fingerprints"":[""There isn't a GitHub Pages site here""]}"
```

### JSON

```json
[
  {
    "subdomain": "blog.example.com",
    "cname": "blog.example.com.github.io",
    "service": "GitHub Pages",
    "severity": "high",
    "status": "vulnerable",
    "detail": {
      "cname_matched": "\\.github\\.io$",
      "dns_status": "NOERROR",
      "http_path": "/",
      "http_status": 404,
      "matched_fingerprints": ["There isn't a GitHub Pages site here"],
      "missed_fingerprints": []
    }
  }
]
```

## 实施优先级（Review 后调整）

| 优先级 | 事项 |
|--------|------|
| P0 | CNAME 查询异常细分（NXDOMAIN vs 超时） |
| P0 | `TakeoverResult` dataclass 统一 |
| P1 | `paths` 并行遍历策略（取最高风险） |
| P1 | `detail` 结构化输出 |
| P2 | DNS CNAME `@lru_cache` |
| P2 | 指纹热加载（自定义路径 + reload） |
| P3 | NS 接管检测（二期实现，扩展 `ns_takeover` 字段和 `ns_patterns`） |
