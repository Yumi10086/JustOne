# JustOne 项目开发日志

## 2026-06-09 — DNS 检查并发化、SOCKS5 回退、DNSSEC 修复、CSV 输入支持

### 背景

本次会话对 JustOne 项目进行了系统性代码审查与性能修复，涉及 check 命令的性能瓶颈、
代理容错、输入兼容性等问题。

### 一、DNSCheck 串行 → 并发 (ThreadPoolExecutor)

**问题**: DNSCheck.run() 使用纯 for 循环逐条解析 DNS，500 个子域名需约 500+ 秒，
与 AsyncHTTPCheck 的 aiohttp 100 并发形成巨大反差。

**修复**: modules/check/dns.py — 引入 ThreadPoolExecutor(max_workers=200)，
与 Brute 模块保持一致的并发模式。新增 concurrent 参数（默认 200）。

**验证**: 5 个 baidu.com 子域名解析耗时从 ~5s 降至 0.10s。
test_check_dns.py 10 passed / 3 skipped / 0 failures。

### 二、CDNCheck 串行 → 并发 (ThreadPoolExecutor)

**问题**: CDNCheck.run() 同样为串行循环，每个子域名做 CNAME 查询 + IP 解析，
在大量存活子域名场景下严重拖慢整体流程。

**修复**: modules/check/cdn.py — 引入 ThreadPoolExecutor(max_workers=100)，
新增 concurrent 参数（默认 100）。

### 三、CLI check 命令增强

**新增参数**:
- --dns-concurrent / -dc : DNS 解析并发数（默认 200）
- --cdn-concurrent / -cc : CDN 识别并发数（默认 100）

**CSV 输入支持**: -i 参数现在支持 CSV 文件，自动检测格式（逗号检测），
跳过表头行，提取 subdomain/domain/url/host 列。

### 四、DNSSEC 在 -i 模式下被静默跳过

**问题**: check 命令中 `if dns_security and target:` — 当使用 -i 时 target 为 None，
整块 DNSSEC 检测被跳过，无任何提示。

**修复**: -i 模式下从第一个子域名自动提取注册域名作为 main_domain；
条件改为 `if dns_security and main_domain:`。

### 五、SOCKS5 DNS 代理不可用时回退直连

**问题**: 配置 PROXY_ENABLE=true 但代理未运行时，_socks5_tcp 阻塞超时后抛异常，
每个子域名浪费 5-10s，全部返回 0 结果，用户无有效错误提示。

**修复**: common/resolve.py — _socks5_tcp 增加异常捕获：
OSError / ProxyConnectionError / GeneralProxyError → 调用 _orig_tcp 直连；
新增 _warn_socks5_fallback() 全局标志位，仅告警一次避免日志刷屏。

**验证**: 指向不存在的代理 (127.0.0.1:19999)，连续解析 3 个域名：
仅 1 次 WARNING，全部成功解析。

### 六、文档与数据源修正

- README.md: 更新 check 命令使用说明、参数表、代理配置三层策略
- 修复 data source 表: Gitee → GitHub（实际代码无 Gitee 模块）
- 移除不存在的 DNSdb 和 SiteDossier 数据集条目
- 新增 JustOne_项目原理与实现_演讲稿素材.md（24 章节完整分析）

### 修改文件清单

| 文件 | 改动 |
|------|------|
| modules/check/dns.py | for 循环 → ThreadPoolExecutor(200) 并发 |
| modules/check/cdn.py | for 循环 → ThreadPoolExecutor(100) 并发 |
| justone.py | +dc/+cc 参数、CSV 解析、DNSSEC -i 修复 |
| common/resolve.py | SOCKS5 失败回退直连 + 一次性告警 |
| README.md | check 使用说明、代理配置、数据源修正 |
| JustOne_项目原理与实现_演讲稿素材.md | 新增，24 章节完整技术分析 |

### 测试结果

- test_check_dns.py: 10 passed / 3 skipped / 0 failures
- test_check_http.py: 18 passed / 5 skipped / 0 failures
- 功能验证: SOCKS5 回退三次解析全部成功，仅一次 WARNING
- 并发验证: 5 子域名 0.10s（串行约需 5s）

### 提交

commit 4d5894a — 5 files changed, +160/-45 lines

---

*时间: 2026-06-09*
*状态: 全部修改完成并提交*
