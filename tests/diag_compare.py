# -*- coding: utf-8 -*-
"""对比两者差异 —— 逐行复现 resolve_domain 逻辑"""

import sys, socket, time
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import common.resolve as resolve_mod
resolve_mod.init_dns_proxy(['socks5://127.0.0.1:10808'])

import dns.resolver

# ========= 测试 1: 完全模拟 trace_socks5.py 的做法 =========
print("=== 测试1: 手动创建 resolver (trace_socks5.py 的方式) ===")
r1 = dns.resolver.Resolver()
r1.nameservers = resolve_mod.resolve_config['dns_nameservers']
# 不设 timeout/lifetime
try:
    ans = r1.resolve('wx.qq.com', 'A', tcp=True)
    print(f"  ✅ {ans[0]}")
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

# ========= 测试 2: 加 timeout/lifetime =========
print("\n=== 测试2: 手动创建 + timeout=5 lifetime=10 ===")
r2 = dns.resolver.Resolver()
r2.nameservers = resolve_mod.resolve_config['dns_nameservers']
r2.timeout = 5
r2.lifetime = 10
try:
    ans = r2.resolve('wx.qq.com', 'A', tcp=True)
    print(f"  ✅ {ans[0]}")
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

# ========= 测试 3: 走 resolve_domain =========
print("\n=== 测试3: resolve_domain() ===")
result = resolve_mod.resolve_domain('wx.qq.com')
print(f"  → {result}")
