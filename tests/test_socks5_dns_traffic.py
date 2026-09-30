#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SOCKS5 DNS 代理逐层诊断脚本

逐层验证:
  1. PySocks 安装 → socksocket 能否独立工作
  2. socket_factory 替换 → 是否被 dnspython 调用
  3. SOCKS5 握手 → 代理端口是否连接、协商是否成功
  4. DNS 解析 → 最终 DNS 查询是否经代理
  5. 真实抓包 → tcpdump/Wireshark 确认流量走向

用法: python tests/test_socks5_dns_traffic.py
"""

import os
import sys
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# 真实网络依赖（搜索引擎/证书日志/DNS 流量/CLI 端到端）：CI 默认跳过，
# 本地用 pytest -m network 单独运行，或 pytest 全量运行
pytestmark = pytest.mark.network

SOCKS5_PROXY = os.environ.get("SOCKS5_PROXY", "socks5://127.0.0.1:10808")
TARGET_DOMAIN = os.environ.get("TEST_DOMAIN", "wx.qq.com")
PARSED = urlparse(SOCKS5_PROXY)
PROXY_HOST = PARSED.hostname
PROXY_PORT = PARSED.port or 10808

_passed = []
_failed = []


def ok(msg):
    _passed.append(msg)
    print(f"  [OK] {msg}")


def fail(msg):
    _failed.append(msg)
    print(f"  [FAIL] {msg}")


def separator(title):
    print()
    print(f"=== {title} ===")


# ============================================================
separator("第1层: PySocks 库检查")

try:
    import socks as socks_module
    ok(f"PySocks 已安装, socksocket 可用")
except ImportError:
    fail("PySocks 未安装！pip install pysocks")
    sys.exit(1)


separator("第2层: SOCKS5 代理端口连通性")

try:
    s = socks_module.socksocket(socket.AF_INET, socket.SOCK_STREAM)
    s.set_proxy(socks_module.SOCKS5, PROXY_HOST, PROXY_PORT)
    s.settimeout(5)
    s.connect(('1.1.1.1', 80))
    s.close()
    ok(f"SOCKS5 代理 {PROXY_HOST}:{PROXY_PORT} 握手成功")
except Exception as e:
    fail(f"SOCKS5 代理 {PROXY_HOST}:{PROXY_PORT} 握手失败: {e}")
    print("     → 请确认 v2rayN SOCKS5 代理已启动，端口为 {PROXY_PORT}")


separator("第3层: PySocks 独立 DNS 解析测试")

try:
    s = socks_module.socksocket(socket.AF_INET, socket.SOCK_STREAM)
    s.set_proxy(socks_module.SOCKS5, PROXY_HOST, PROXY_PORT, rdns=True)
    s.settimeout(10)
    s.connect(('223.5.5.5', 53))
    ok("SOCKS5 连接 223.5.5.5:53 成功（协商通过）")

    import struct
    import dns.message
    q = dns.message.make_query(TARGET_DOMAIN, 'A')
    wire = q.to_wire()
    tcp_msg = struct.pack("!H", len(wire)) + wire
    s.sendall(tcp_msg)
    resp_len = s.recv(2)
    if len(resp_len) < 2:
        fail("DNS 响应长度接收失败")
    else:
        dns_len = struct.unpack("!H", resp_len)[0]
        resp_data = s.recv(dns_len)
        r = dns.message.from_wire(resp_data)
        ips = [str(a) for a in r.answer if a.rdtype == 1]
        if ips:
            ok(f"DNS 解析成功: {TARGET_DOMAIN} -> {ips}")
        else:
            fail(f"DNS 应答无 A 记录")
    s.close()
except Exception as e:
    fail(f"SOCKS5 独立 DNS 失败: {e}")
    print("     → 检查: v2rayN → 设置 → 路由设置 → 域名策略")
    print("     → 检查: v2rayN DNS 选项卡是否正确配置")


separator("第4层: socket_factory 调用链验证")

import dns.query

from common import resolve
resolve.init_dns_proxy([SOCKS5_PROXY])

if not resolve.is_socks5_dns_enabled():
    fail("is_socks5_dns_enabled() == False, init_dns_proxy 未生效")
else:
    ok("is_socks5_dns_enabled() == True")

factory_call_count = [0]
connect_call_count = [0]
orig_factory = dns.query.socket_factory

def trace_factory(family, kind, proto):
    factory_call_count[0] += 1
    sock = orig_factory(family, kind, proto)
    stype = "TCP" if kind == socket.SOCK_STREAM else "UDP"

    # 判断是否 SOCKS5 socket
    is_socks = isinstance(sock, socks_module.socksocket)

    # 记录真实的 setblocking 行为
    has_noop_setblocking = (getattr(type(sock), 'setblocking', None) is None or
                            not callable(getattr(sock, 'setblocking', None)))

    if is_socks:
        # 临时恢复 setblocking 确认是否已被 patch
        sb = getattr(sock, 'setblocking', None)
        print(f"     [TRACE] socket_factory #{factory_call_count[0]}: {stype}, "
              f"SOCKS5 socket, setblocking={'patched' if callable(sb) and hasattr(sb, '__name__') and sb.__name__ == '<lambda>' else 'raw'}")

        # 拦截 connect_ex 以追踪 SOCKS5 握手
        orig_connect_ex = sock.connect_ex
        def traced_connect_ex(addr):
            connect_call_count[0] += 1
            print(f"     [TRACE] connect_ex #{connect_call_count[0]}: {addr} (触发 SOCKS5 协商)")
            result = orig_connect_ex(addr)
            if result == 0:
                print(f"     [TRACE] connect_ex 结果: 成功")
            else:
                print(f"     [TRACE] connect_ex 结果: 错误码 {result} ({os.strerror(result) if result else 'OK'})")
            return result
        sock.connect_ex = traced_connect_ex
    else:
        print(f"     [TRACE] socket_factory #{factory_call_count[0]}: {stype}, 普通 socket (未走 SOCKS5!)")

    return sock

dns.query.socket_factory = trace_factory

print(f"  使用域名 {TARGET_DOMAIN} 进行 DNS 解析")
print(f"  请在 Wireshark 中监控 loopback 接口")
print()

info = resolve.resolve_domain(TARGET_DOMAIN)

separator("第5层: 结果汇总")
print(f"  socket_factory 被调用: {factory_call_count[0]} 次")
print(f"  connect_ex 被调用: {connect_call_count[0]} 次")

if info and info.get('ip'):
    print(f"  DNS 结果: {TARGET_DOMAIN} -> {info['ip']}")
else:
    print(f"  DNS 失败: {info.get('reason', '?') if info else 'None'}")

dns.query.socket_factory = orig_factory
resolve.init_dns_proxy([])

print()
print(f"通过: {len(_passed)}, 失败: {len(_failed)}")
if _failed:
    for f in _failed:
        print(f"  ✗ {f}")
