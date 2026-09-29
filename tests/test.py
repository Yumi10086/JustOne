import socks
import socket
import dns.resolver
from queue import Queue
import threading

# ======== SOCKS5 代理配置 ========
SOCKS5_ADDR = "127.0.0.1"   # 代理IP
SOCKS5_PORT = 10808         # 代理端口
SOCKS5_USER = None          # 用户名（无认证可设为 None）
SOCKS5_PASS = None          # 密码（无认证可设为 None）

# 设置全局 SOCKS5 代理，并开启远程 DNS 解析（避免本地 DNS 泄露）
socks.set_default_proxy(
    proxy_type=socks.SOCKS5,
    addr=SOCKS5_ADDR,
    port=SOCKS5_PORT,
    username=SOCKS5_USER,
    password=SOCKS5_PASS,
    rdns=True
)
socket.socket = socks.socksocket  # 替换默认 socket

# ======== 爆破线程类 ========
class DNSBruteThread(threading.Thread):
    def __init__(self, queue, domain, results):
        super().__init__()
        self.queue = queue
        self.domain = domain
        self.results = results
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 3
        self.resolver.lifetime = 3

    def run(self):
        while not self.queue.empty():
            sub = self.queue.get()
            fqdn = f"{sub}.{self.domain}"
            try:
                answers = self.resolver.resolve(fqdn, "A")
                ips = [rdata.address for rdata in answers]
                print(f"[+] {fqdn} -> {ips}")
                self.results.append((fqdn, ips))
            except Exception:
                pass
            finally:
                self.queue.task_done()

# ======== 主程序 ========
def dns_brute(domain, wordlist, threads=5):
    queue = Queue()
    results = []

    # 读取字典
    with open(wordlist, "r", encoding="utf-8") as f:
        for line in f:
            sub = line.strip()
            if sub:
                queue.put(sub)

    # 启动线程
    workers = []
    for _ in range(threads):
        t = DNSBruteThread(queue, domain, results)
        t.start()
        workers.append(t)

    # 等待完成
    queue.join()
    for t in workers:
        t.join()

    return results

if __name__ == "__main__":
    target_domain = "example.com"   # 目标域名
    wordlist_file = "E:\\文件\\JustOne\\data\\subnames.txt"  # 子域名字典文件

    found = dns_brute(target_domain, wordlist_file, threads=10)

    print("\n=== 爆破结果 ===")
    for fqdn, ips in found:
        print(f"{fqdn} -> {', '.join(ips)}")
