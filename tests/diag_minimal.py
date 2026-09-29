# -*- coding: utf-8 -*-
"""SOCKS5 DNS 代理诊断 — 极简版，无 monkey-patch"""

import sys, socket, time
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import common.resolve as resolve_mod

# ---- Step 1: 端口可达 ----
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(3)
if s.connect_ex(('127.0.0.1', 10808)) != 0:
    print("❌ 10808 不可达"); sys.exit(1)
s.close()
print("✅ 10808 可达")

# ---- Step 2: 初始化 ----
resolve_mod.init_dns_proxy(['socks5://127.0.0.1:10808'])
print(f"✅ enabled={resolve_mod._socks5_enabled}")

# ---- Step 3: 直接测试 resolve_domain ----
import dns.query
print(f"   factory before={dns.query.socket_factory.__name__}")

for domain in ['wx.qq.com', 'www.baidu.com']:
    print(f"\n  {domain} ...", end=' ', flush=True)
    start = time.time()
    result = resolve_mod.resolve_domain(domain)
    elapsed = time.time() - start
    if result and result.get('resolve') == 1:
        print(f"✅ {result.get('ip')} ({elapsed:.2f}s)")
    else:
        reason = result.get('reason', 'None') if result else 'None'
        print(f"❌ {reason} ({elapsed:.2f}s)")
