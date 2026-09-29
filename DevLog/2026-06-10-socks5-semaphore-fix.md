# JustOne 项目开发日志

## 2026-06-10 — SOCKS5 DNS 代理并发修复 + 诊断脚本修复

### 问题

SOCKS5 DNS 代理在启用状态下持续报 WARNING `SOCKS5 DNS 代理不可用，已自动回退直连 DNS`。
实际代理客户端运行正常，但 `check --dns`（200 并发）和 brute（2000 并发）同时打代理导致连接被拒绝/超时。
此外 `tests/diagnose_socks5_dns.py` 在 Step 4 崩溃（`AttributeError: _socks5_socket_factory`），无法完成诊断。

### 一、诊断脚本修复

**问题**: 诊断脚本引用 `resolve_mod._socks5_socket_factory`，但当前实现是替换 `dns.query.tcp` 函数而非 `socket_factory`。
Step 4 始终崩溃，导致 Step 5/6 无法执行。

**修改**: `tests/diagnose_socks5_dns.py`
- Step 4 改为检查 `dns.query.tcp` 是否已替换为 `_socks5_tcp`
- Step 5 改为 trace `dns.query.tcp` 调用（原为 trace `socket_factory`）
- 增加失败计数和错误详情展示

### 二、_socks5_tcp 增加异常日志

**问题**: 捕获异常后无日志，无法判断是 timeout、connection refused 还是 auth 失败。

**修改**: `common/resolve.py:98-100`
- `except` 块增加 `as e`，用 `logger.debug` 记录具体异常类型和信息

### 三、SOCKS5 并发限制（信号量）

**根因**: `_socks5_tcp` 无并发控制。200（check）或 2000（brute）个线程同时创建 SOCKS5 socket 连接代理，
代理服务器连接数上限被击穿，后续连接全部被拒。

**修改**: `common/resolve.py`
- 新增 `import threading`
- 新增 `_socks5_semaphore = threading.Semaphore(32)` 限制同时 SOCKS5 连接数
- `_socks5_tcp` 重构：SOCKS5 连接代码包裹在 `with _socks5_semaphore` 内，
  回退直连 DNS 的 `_orig_tcp` 调用放在信号量外部执行，避免占用槽位

**验证**:
- 诊断脚本 6 步全部通过，SOCKS5 DNS 解析正常（wx.qq.com / www.baidu.com 均成功，0.05s）
- 压力测试：100 域名 × 200 worker 并发 → 100/100 成功，0.5s，无 WARNING
- test_check_dns.py: 10 passed / 3 skipped / 0 failures

### 修改文件清单

| 文件 | 改动 |
|------|------|
| common/resolve.py | +import threading，+Semaphore(32)，_socks5_tcp 重构（with semaphore），异常日志 |
| tests/diagnose_socks5_dns.py | Step 4 修复 _socks5_socket_factory → dns.query.tcp 检查，Step 5-6 适配 |

---

*时间: 2026-06-10*
*状态: 修改完成，待提交*
