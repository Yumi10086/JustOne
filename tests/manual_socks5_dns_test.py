# -*- coding: utf-8 -*-
"""
SOCKS5 DNS 代理手动验证脚本

通过 Wireshark 抓包验证 DNS 查询是否经过 SOCKS5 代理转发。
不涉及 brute/altdns 模块，仅测试 DNS 解析通路。
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from common.resolve import init_dns_proxy, resolve_domain, is_socks5_dns_enabled

# 测试域名（使用国内 DNS 可能被污染的域名）
TEST_DOMAINS = [
    'wx.qq.com',
    'www.google.com',
    'github.com',
]

def main():
    print('=' * 60)
    print('SOCKS5 DNS 代理验证测试')
    print('=' * 60)

    # Step 1: 初始化 DNS 代理
    print('\n[1] 初始化 DNS 代理...')
    proxy_pool = ['socks5://127.0.0.1:10808']
    init_dns_proxy(proxy_pool)

    enabled = is_socks5_dns_enabled()
    print(f'    SOCKS5 DNS 代理状态: {"已启用" if enabled else "未启用"}')
    if not enabled:
        print('    错误: SOCKS5 DNS 代理未成功启用，退出')
        sys.exit(1)

    # Step 2: 执行 DNS 解析
    print('\n[2] 执行 DNS 解析（通过 SOCKS5 代理）...')
    for domain in TEST_DOMAINS:
        print(f'\n    解析: {domain}')
        start = time.time()
        result = resolve_domain(domain)
        elapsed = time.time() - start

        if result and result.get('resolve') == 1:
            print(f'    结果: {result.get("ip", "N/A")}')
            if result.get('cname'):
                print(f'    CNAME: {result.get("cname")}')
            print(f'    耗时: {elapsed:.2f}s')
        else:
            reason = result.get('reason', 'Unknown') if result else 'None'
            print(f'    失败: {reason} ({elapsed:.2f}s)')

    print('\n' + '=' * 60)
    print('测试完成 — 请检查 Wireshark 抓包结果')
    print('=' * 60)


if __name__ == '__main__':
    main()
