# -*- coding: utf-8 -*-
"""
SOCKS5 DNS 代理诊断脚本 v2

逐层排查失败原因。使用模块引用避免 import 缓存问题。
"""

import sys
import socket
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import common.resolve as resolve_mod

# ============================================================
# Step 1: 检查 SOCKS5 代理是否在监听
# ============================================================
print("=" * 60)
print("Step 1: 代理端口 127.0.0.1:10808 可达性")
print("=" * 60)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(3)
try:
    result = sock.connect_ex(('127.0.0.1', 10808))
    if result == 0:
        print("  ✅ 代理端口 127.0.0.1:10808 可达")
    else:
        print(f"  ❌ 代理端口不可达，connect_ex={result}")
        print("  → 请确保 SOCKS5 代理客户端正在运行")
        sys.exit(1)
finally:
    sock.close()

# ============================================================
# Step 2: PySocks + 原始 SOCKS5 连接测试
# ============================================================
print("\n" + "=" * 60)
print("Step 2: PySocks 导入 & 原始 SOCKS5 连接")
print("=" * 60)

try:
    import socks as socks_module
    print(f"  ✅ PySocks: {socks_module.__file__}")
except ImportError as e:
    print(f"  ❌ PySocks 未安装: {e}")
    sys.exit(1)

# 原始 SOCKS5 连接 → DNS 服务器
try:
    s = socks_module.socksocket(socket.AF_INET, socket.SOCK_STREAM)
    s.set_proxy(socks_module.SOCKS5, '127.0.0.1', 10808, rdns=True)
    s.settimeout(5)
    start = time.time()
    s.connect(('223.5.5.5', 53))
    print(f"  ✅ SOCKS5 → 223.5.5.5:53 成功 ({time.time()-start:.2f}s)")
    s.close()
except Exception as e:
    print(f"  ❌ SOCKS5 原始连接失败: {type(e).__name__}: {e}")
    sys.exit(1)

# ============================================================
# Step 3: init_dns_proxy() 初始化 (模块级访问)
# ============================================================
print("\n" + "=" * 60)
print("Step 3: init_dns_proxy() 初始化")
print("=" * 60)

print(f"  init 前: _socks5_enabled={resolve_mod._socks5_enabled}")
resolve_mod.init_dns_proxy(['socks5://127.0.0.1:10808'])
print(f"  init 后: _socks5_enabled={resolve_mod._socks5_enabled}")
print(f"  init 后: _socks5_proxies={resolve_mod._socks5_proxies}")
print(f"  is_socks5_dns_enabled()={resolve_mod.is_socks5_dns_enabled()}")

if not resolve_mod._socks5_enabled:
    print("  ❌ 未启用，退出")
    sys.exit(1)
print("  ✅ 已启用")

# ============================================================
# Step 4: dns.query.tcp 替换验证
# ============================================================
print("\n" + "=" * 60)
print("Step 4: dns.query.tcp 替换验证")
print("=" * 60)

import dns.query
print(f"  dns.query.tcp        = {dns.query.tcp}")
print(f"  resolve_mod._socks5_tcp  = {resolve_mod._socks5_tcp}")
print(f"  resolve_mod._orig_tcp    = {resolve_mod._orig_tcp}")
print(f"  已替换为 SOCKS5?    = {dns.query.tcp is resolve_mod._socks5_tcp}")

if dns.query.tcp is not resolve_mod._socks5_tcp:
    print("  ❌ dns.query.tcp 未被替换为 SOCKS5 版本")
    sys.exit(1)
print("  ✅ dns.query.tcp 已替换为 _socks5_tcp")

# ============================================================
# Step 5: trace dns.query.tcp 调用（验证 SOCKS5 路径是否被使用）
# ============================================================
print("\n" + "=" * 60)
print("Step 5: trace dns.query.tcp 调用")
print("=" * 60)

original_tcp = dns.query.tcp
tcp_called = [0]
tcp_success = [0]
tcp_errors = []

def tracing_tcp(q, where, timeout=None, port=53, **kwargs):
    """带计数的 dns.query.tcp wrapper"""
    tcp_called[0] += 1
    print(f"  [TRACE] tcp #{tcp_called[0]}: → {where}:{port}, timeout={timeout}")
    start = time.time()
    try:
        result = original_tcp(q, where, timeout=timeout, port=port, **kwargs)
        elapsed = time.time() - start
        tcp_success[0] += 1
        print(f"  [TRACE] tcp #{tcp_called[0]}: ✅ 成功 ({elapsed:.2f}s)")
        return result
    except Exception as e:
        elapsed = time.time() - start
        tcp_errors.append(f'#{tcp_called[0]} {type(e).__name__}: {e}')
        print(f"  [TRACE] tcp #{tcp_called[0]}: ❌ {type(e).__name__}: {e} ({elapsed:.2f}s)")
        raise

dns.query.tcp = tracing_tcp

# ============================================================
# Step 6: resolve_domain() 测试
# ============================================================
print("\n" + "=" * 60)
print("Step 6: resolve_domain() 测试")
print("=" * 60)

print(f"  _socks5_enabled = {resolve_mod._socks5_enabled}")
print(f"  → resolve 将使用 tcp={resolve_mod._socks5_enabled}")

test_domains = ['wx.qq.com', 'www.baidu.com']
for domain in test_domains:
    print(f"\n  解析: {domain} ...")
    start = time.time()
    result = resolve_mod.resolve_domain(domain)
    elapsed = time.time() - start

    if result:
        if result.get('resolve') == 1:
            print(f"  ✅ {domain} → {result.get('ip', 'N/A')} ({elapsed:.2f}s)")
        else:
            print(f"  ❌ {domain} 失败: {result.get('reason')} ({elapsed:.2f}s)")
    else:
        print(f"  ❌ {domain} 返回 None ({elapsed:.2f}s)")

print(f"\n  dns.query.tcp 被调用次数: {tcp_called[0]}")
print(f"  成功次数: {tcp_success[0]}")
if tcp_errors:
    print(f"  失败详情:")
    for err in tcp_errors:
        print(f"    - {err}")
if tcp_called[0] == 0:
    print("  ⚠️  dns.query.tcp 未被调用！dnspython 可能未使用 TCP 模式")
elif tcp_errors:
    print("  ⚠️  有 tcp 调用失败，请查看上方错误详情")
else:
    print("  ✅ 所有 tcp 调用成功")

# 恢复
dns.query.tcp = original_tcp

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
