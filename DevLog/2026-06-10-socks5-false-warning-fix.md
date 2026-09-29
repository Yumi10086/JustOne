# JustOne 项目开发日志

## 2026-06-10 — SOCKS5 DNS 虚假警告修复 + 并发控制

### 问题

用户反馈运行 `check --dns` 时持续报 `WARNING: SOCKS5 DNS 代理不可用，已自动回退直连 DNS`，
但实际代理客户端（v2rayN）运行正常，且 224/324 子域名通过 SOCKS5 成功解析（6s 完成）。

### 根因分析

经逐步排查：

1. **代理连通性验证**：`socks.socksocket` 直连 `127.0.0.1:10808`，SOCKS5 握手正常（05 01 00 -> 05 00）
2. **并发压测**：10/50/100/200 并发纯 SOCKS5 DNS 查询，全部 100/100 成功，零失败
3. **代码路径测试**：`resolve_domain()` 330 并发 -> 330/330 成功，0.98s，无警告
4. **时序分析**：用户日志显示：
   - 00:46:19 启动，309/324 在 1 秒内完成
   - 00:46:25 WARNING 触发（恰好 5 秒后 = DNS 超时）
   - 剩余 15 个不可解析域名在 5s 超时后完成

**真正根因**：`_socks5_tcp` 异常捕获过于宽泛 -> `except (OSError, ...)`。

Python 3 中 `socket.timeout` 是 `OSError` 的子类。不可解析域名的 DNS 查询触发 5 秒超时
(`socket.timeout`) 被误判为代理故障，错误触发 WARNING。
实际代理对可解析域名完全正常工作（309 个在 1s 内完成）。

### 修复

#### 一、异常分类处理

`common/resolve.py` — `_socks5_tcp` 异常捕获拆分为三层：

| 异常类型 | 含义 | 行为 |
|----------|------|------|
| `ProxyConnectionError` / `GeneralProxyError` / `ConnectionRefusedError` | 代理真的不可用 | [WARNING] WARNING + 回退直连 |
| `socket.timeout` / `TimeoutError` | DNS 查询超时（非代理故障） | 静默回退直连 |
| 其他 `OSError` | 网络波动（连接重置等） | 静默回退直连 |

每层异常均保留 `logger.debug` 日志方便排查。

#### 二、SOCKS5 并发控制（信号量）

**问题**：`_socks5_tcp` 无并发控制，200（check）或 2000（brute）线程同时创建 SOCKS5 连接，
代理服务器连接数上限被击穿。

**修复**：
- 新增 `import threading`
- 新增 `_socks5_semaphore = threading.Semaphore(32)`
- `_socks5_tcp` 重构：SOCKS5 连接代码包裹在 `with _socks5_semaphore` 内
- 回退直连 DNS 的 `_orig_tcp` 调用放在信号量外部，不占用 SOCKS5 槽位

### 验证

| 场景 | 结果 |
|------|------|
| `check --dns` on 324 bilibili 子域名 | 224 resolved, 6.1s, 无 WARNING |
| 代理宕机（指向不存在端口 127.0.0.1:19999） | WARNING 正确触发，仅一次 |
| `test_check_dns.py` | 10 passed / 3 skipped / 0 failures |
| 语法检查 | Syntax OK |

### 修改文件清单

| 文件 | 改动 |
|------|------|
| common/resolve.py | +import threading，+Semaphore(32)，_socks5_tcp 三层异常处理重构，回退逻辑移到信号量外部 |

### 提交

commit 65f9b48 — 1 file changed, +56/-39 lines

---

*时间: 2026-06-10*
*状态: 修复完成并提交*
