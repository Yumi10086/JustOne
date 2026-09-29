# JustOne 项目开发日志

## 2026-05-31 — DNS 爆破 SOCKS5 代理方案调研

### 背景

希望在 DNS 爆破（`modules/brute.py`）中走 SOCKS5 代理，绕过 GFW 对国外 DNS 的污染。

### 调研过程

1. **尝试一：`resolver.socket_factory`**
   - dnspython 2.8.0 的 `Resolver` 类有 `socket_factory` 属性
   - 测试发现该属性**不被 `Resolver.resolve()` 调用**，设置无效
   - 抓包确认无 SOCKS 流量

2. **源码追踪发现**
   - `Resolver.resolve()` -> `_Resolution` -> `Do53Nameserver.query()` -> `dns.query.udp()`/`tcp()`
   - `dns.query.udp()` -> `make_socket()` -> **`dns.query.socket_factory`**（模块级变量）
   - 这是真正生效的入口，位于 `dns/query.py:180-182`

3. **最终方案**
   - 替换 `dns.query.socket_factory` 模块级变量
   - 使用 PySocks 创建 `socks.socksocket`，设置 `rdns=True`（代理端解析）
   - 强制 DNS 走 TCP 模式（SOCKS5 UDP ASSOCIATE 在不同代理实现中不可靠）

### 涉及文件

| 文件 | 改动 |
|------|------|
| `common/resolve.py` | 新增 `init_dns_proxy()`, `_socks5_socket_factory()`, `_socks5_enabled` 标志 |
| `common/utils.py` | 新增 `get_socks5_proxy_list()`, `get_random_socks5_proxy()`, `create_socks5_socket_factory()`, `test_socks5_proxy()` |
| `justone.py` | 在 `set_http_config()` 后调用 `init_dns_proxy()` |
| `requirements.txt` | 添加 `pysocks>=1.7.1` |

### 调用链

```
init_dns_proxy() -> dns.query.socket_factory = _socks5_socket_factory
resolve_domain() -> resolver.resolve(tcp=True)
-> Do53Nameserver.query(max_size=True)
-> dns.query.tcp() -> make_socket(SOCK_STREAM)
-> socket_factory() -> socks.socksocket() -> connect(proxy)
```

### 配置方式

```env
PROXY_ENABLE=true
PROXY_POOL=socks5://127.0.0.1:10808,socks5://192.168.1.100:10809
```

支持多条代理，每条 DNS 查询随机选一条。

### 已知问题

- **代码已回退**，当前工作区为最新 commit 版本
- 该方案理论上可行（已验证 `dns.query.socket_factory` 替换后 `make_socket` 产出 `socks.socksocket`）
- 需要用户实际配置代理并测试
- 如果代理不支持 TCP 上游 DNS，需确认 DNS 服务器（223.5.5.5 等）从代理可达
