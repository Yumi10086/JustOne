# -*- coding: utf-8 -*-
"""终极诊断：instrument dnspython 的 _connect 看看到底卡在哪里"""

import sys, errno, os, socket, time, select
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import common.resolve as resolve_mod
resolve_mod.init_dns_proxy(['socks5://127.0.0.1:10808'])

# ---- Monkey-patch: 替换 dnspython 的 _connect，用 connect() 而不是 connect_ex() ----
import dns.query

_orig_make_socket = dns.query.make_socket
_orig_connect = dns.query._connect

def patched_make_socket(af, type, source=None):
    """创建 socket 但不调用 setblocking(False)，保持阻塞模式"""
    s = dns.query.socket_factory(af, type, 0)
    if source is not None:
        s.bind(source)
    return s

def patched_connect(s, address, expiration):
    """用 connect() 代替 connect_ex()，加追踪"""
    deadline = expiration - time.time()
    print(f"    [_connect] target={address}, timeout={deadline:.1f}s, socket_type={type(s).__name__}")
    s.settimeout(max(deadline, 1))
    try:
        s.connect(address)
        print(f"    [_connect] ✅ connected")
    except Exception as e:
        print(f"    [_connect] ❌ {type(e).__name__}: {e}")
        raise

dns.query.make_socket = patched_make_socket
dns.query._connect = patched_connect

# ---- 测试 ----
print("=== 测试: resolve_domain() ===")
import time
for domain in ['wx.qq.com', 'www.baidu.com']:
    print(f"\n  {domain} ...")
    start = time.time()
    result = resolve_mod.resolve_domain(domain)
    elapsed = time.time() - start
    if result and result.get('resolve') == 1:
        print(f"  ✅ {result.get('ip')} ({elapsed:.2f}s)")
    else:
        print(f"  ❌ {result.get('reason', 'None') if result else 'None'} ({elapsed:.2f}s)")

# ---- 恢复 ----
dns.query.make_socket = _orig_make_socket
dns.query._connect = _orig_connect
