# JustOne 项目开发日志

## 2026-06-05 — SOCKS5 DNS 代理实现与联调

### 背景

需要通过 SOCKS5 代理转发 DNS 查询，绕过 GFW 的 DNS 污染。
之前 2026-05-31 已实现基础版本，但经测试发现在不同环境下行为不一致。

### 工作内容

#### 一、问题定位

**现象**: manual_socks5_dns_test.py 测试 DNS 解析全部超时(11.11s)，
Wireshark 抓包显示 10808 端口流量为 TLS(17 03 03) 而非 SOCKS5(05 01 00)。

**根因**: v2rayN 开启了 TUN 模式，10808 端口运行的是 VMess/TLS 协议，
不接受 SOCKS5 握手。TUN 模式通过虚拟网卡拦截流量，不开放 SOCKS5 入站。

**解决**: v2rayN 关闭 TUN 模式，配置 SOCKS5 入站:


#### 二、dnspython 兼容性修复

**问题 1 — socket_factory 不被调用**: dnspython 的 make_socket() 在创建 socket 后
立即调用 setblocking(False)，PySocks 的 SOCKS5 握手需要阻塞 I/O，
非阻塞模式下 connect_ex() 失败。

**初始方案**: 在 socket_factory 中 patch setblocking 为 no-op，阻止 dnspython 设为非阻塞。
这在部分环境有效，但不稳定。

**问题 2 — make_socket 不存在**: 用户环境的 dnspython 2.8.0 构建版本缺少
dns.query.make_socket 导出，导致替换方案不完整。

**最终方案**: 直接替换 dns.query.tcp 函数，用纯 PySocks 实现 DNS-over-TCP。
绕过所有 dnspython 内部函数兼容性问题。

#### 三、代码改动

文件: common/resolve.py

新增 _socks5_tcp() 函数:
- 创建 PySocks socksocket，直接 CONNECT 到 DNS 服务器
- 手动发送 DNS wire-format 查询(TCP 前缀 2 字节长度)
- 接收并解析 DNS 响应
- 不依赖 dnspython 的 socket_factory / make_socket / _connect

init_dns_proxy() 改动:
- 启用时: dns.query.tcp = _socks5_tcp
- 禁用时: dns.query.tcp = _orig_tcp(恢复原始)

#### 四、验证方法

1. v2rayN SOCKS5 入站就绪: netstat -ano | findstr "10808" 显示 LISTENING
2. 原始 SOCKS5 连通: socks5_raw_test.py — PySocks 直连测试全部通过
3. dnspython 集成: diag_minimal.py / manual_socks5_dns_test.py — resolve_domain() 成功
4. Wireshark 抓包: tcp.port==10808 流量，payload 以 05 01 00 开头，确认为 SOCKS5 握手

### 测试脚本

| 脚本 | 用途 |
|------|------|
| tests/socks5_raw_test.py | 绕过 dnspython，直接测试 SOCKS5 连接 |
| tests/diag_minimal.py | 最简 resolve_domain() 测试，无 monkey-patch |
| tests/manual_socks5_dns_test.py | 完整多域名 DNS 解析测试 |
| tests/trace_socks5.py | 深度 trace dnspython 内部调用链 |

### 后续

- 待完成: 用 Wireshark MCP 抓包验证 SOCKS5 DNS 流量
- 待完成: 集成到 justone.py 主流程的 collect/brute 等模块中测试

---

*时间: 2026-06-05*
*状态: SOCKS5 DNS 代理功能完成，待流量验证*
