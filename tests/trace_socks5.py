# -*- coding: utf-8 -*-
"""深度 trace：打印 dnspython resolver 内每一步的决策"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import common.resolve as resolve_mod
resolve_mod.init_dns_proxy(['socks5://127.0.0.1:10808'])

import dns.resolver
import dns.query

# Monkey-patch：追踪 socket_factory
call_count = [0]
_orig = dns.query.socket_factory

def trace_factory(family, kind, proto):
    call_count[0] += 1
    print(f"  [socket_factory #{call_count[0]}] family={family} kind={kind} proto={proto}")
    return _orig(family, kind, proto)

dns.query.socket_factory = trace_factory

# Monkey-patch：追踪 Do53Nameserver.query
import dns.nameserver
_orig_do53_query = dns.nameserver.Do53Nameserver.query

def traced_query(self, request, timeout, source, source_port, max_size, **kw):
    print(f"  [Do53Nameserver] {self.address}:{self.port} max_size={max_size}")
    return _orig_do53_query(self, request, timeout, source, source_port, max_size, **kw)

dns.nameserver.Do53Nameserver.query = traced_query

# 测试
print("=" * 50)
print(f"_socks5_enabled = {resolve_mod._socks5_enabled}")
print(f"socket_factory is ours = {dns.query.socket_factory is resolve_mod._socks5_socket_factory}")
print(f"nameservers = {resolve_mod.resolve_config['dns_nameservers']}")

resolver = dns.resolver.Resolver()
resolver.nameservers = resolve_mod.resolve_config['dns_nameservers']
resolver.timeout = 5
resolver.lifetime = 10

import time
start = time.time()
try:
    result = resolver.resolve('wx.qq.com', 'A', tcp=resolve_mod._socks5_enabled)
    for rr in result:
        print(f"  ✅ {rr}")
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")
elapsed = time.time() - start

print(f"\nsocket_factory 调用次数: {call_count[0]}")
print(f"耗时: {elapsed:.2f}s")
