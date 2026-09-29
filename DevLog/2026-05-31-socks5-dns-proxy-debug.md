# JustOne 项目开发日志

## 2026-05-31 — SOCKS5 DNS 代理实现与调试

### 背景

需要 DNS 模块（）通过 SOCKS5 代理绕过 GFW 对境外 DNS 的污染。

### 实现方案

采用 dnspython 的  注入点，替换为 PySocks 的 socksocket 工厂，
使所有 DNS 查询经由 SOCKS5 代理转发。SOCKS5 UDP ASSOCIATE 在跨实现中不可靠，强制 TCP 模式。

### 涉及文件

| 文件 | 改动 |
|------|------|
|  | 新增 , , ;  在启用时强制  |
|  | 新增 , ,  |
|  | 启动时调用  |
|  | 新增  |
| 
=== 第1层: PySocks 库检查 ===
  [OK] PySocks 已安装, socksocket 可用

=== 第2层: SOCKS5 代理端口连通性 ===
  [OK] SOCKS5 代理 127.0.0.1:10808 握手成功

=== 第3层: PySocks 独立 DNS 解析测试 ===
  [OK] SOCKS5 连接 223.5.5.5:53 成功（协商通过）
  [OK] DNS 解析成功: wx.qq.com -> ['wx1.qq.com. 74 IN A 101.89.47.179']

=== 第4层: socket_factory 调用链验证 ===
  [OK] is_socks5_dns_enabled() == True
  使用域名 wx.qq.com 进行 DNS 解析
  请在 Wireshark 中监控 loopback 接口

     [TRACE] socket_factory #1: TCP, SOCKS5 socket, setblocking=patched
     [TRACE] connect_ex #1: ('223.5.5.5', 53) (触发 SOCKS5 协商)
     [TRACE] connect_ex 结果: 成功
     [TRACE] socket_factory #2: TCP, SOCKS5 socket, setblocking=patched
     [TRACE] connect_ex #2: ('223.5.5.5', 53) (触发 SOCKS5 协商)
     [TRACE] connect_ex 结果: 成功

=== 第5层: 结果汇总 ===
  socket_factory 被调用: 2 次
  connect_ex 被调用: 2 次
  DNS 结果: wx.qq.com -> 101.89.47.179

通过: 5, 失败: 0 | 五层诊断脚本 |
|  | 清理 Playwright 重复代码块 |

### 排查出的 Bug（3个）

| Bug | 根因 | 修复 |
|-----|------|------|
| DNS 直连 53，不走 SOCKS5 | dnspython 的  调用 ，PySocks 的 SOCKS5 握手（connect 内部）在非阻塞模式下超时 → except 静默回退普通 socket |  阻止非阻塞 |
|  |  参数名  遮蔽了内置  函数， 调用失败 | 参数重命名为  |
| DNS 全部 Timeout |  声明时缺  参数（绑定方法自动传入），raise TypeError → 所有 connect_ex 失败 | 加  参数 |

### 验证结果

- netstat 捕获到 
- DNS 解析成功通过 SOCKS5 代理返回结果
- Wireshark loopback 抓包待 Npcap 配置后验证（Adapter for loopback traffic capture 接口）
- pytest: 60 passed (test_resolve + test_altdns)

### 待办

- 通过 Wireshark MCP 检查 Adapter for loopback traffic capture 上  的流量
- 确认 SOCKS 协议解码

---

*时间: 2026-05-31*
*状态: Wireshark 验证中*
