# -*- coding: utf-8 -*-
"""精确定位：代理能握手，但能不能转发 DNS 连接"""

import sys, socket, time, struct
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import socks

print("=== 测试1: SOCKS5 直连代理 ===")
s = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
s.set_proxy(socks.SOCKS5, '127.0.0.1', 10808)
s.settimeout(5)
try:
    s.connect(('223.5.5.5', 53))
    print("  ✅ 代理接受了 CONNECT → 223.5.5.5:53")
    
    # 发一个 DNS 查询
    q = b'\x00\x1b\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'
    q += b'\x02wx\x02qq\x03com\x00'  # wx.qq.com
    q += b'\x00\x01\x00\x01'  # Type A, Class IN
    
    s.sendall(struct.pack('!H', len(q)) + q)
    resp_len = struct.unpack('!H', s.recv(2))[0]
    resp = b''
    while len(resp) < resp_len:
        resp += s.recv(resp_len - len(resp))
    
    # 解析 IP
    ip = '.'.join(str(b) for b in resp[-4:])
    print(f"  ✅ DNS 查询成功: wx.qq.com → {ip}")
    s.close()
except Exception as e:
    print(f"  ❌ 失败: {type(e).__name__}: {e}")

print("\n=== 测试2: 对比 — 连 HTTPS 端口 ===")
s2 = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
s2.set_proxy(socks.SOCKS5, '127.0.0.1', 10808)
s2.settimeout(5)
try:
    s2.connect(('www.baidu.com', 443))
    print("  ✅ 代理接受了 CONNECT → www.baidu.com:443")
    s2.close()
except Exception as e:
    print(f"  ❌ 失败: {type(e).__name__}: {e}")

print("\n=== 测试3: 对比 — 连 DNS 端口，不同 DNS ===")
for dns_ip in ['223.5.5.5', '8.8.8.8', '1.1.1.1']:
    s3 = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
    s3.set_proxy(socks.SOCKS5, '127.0.0.1', 10808)
    s3.settimeout(5)
    try:
        s3.connect((dns_ip, 53))
        print(f"  ✅ {dns_ip}:53 通过")
        s3.close()
    except Exception as e:
        print(f"  ❌ {dns_ip}:53 失败: {type(e).__name__}: {e}")
