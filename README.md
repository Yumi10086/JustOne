# JustOne

> 子域名收集工具 | Subdomain Collection Tool

基于 Python 3.14 的现代化子域名收集工具，支持多源收集、爆破、置换扩展、存活验证、DNS 安全检测及接管风险检测。

## 功能

- **多源收集** — 12 个搜索引擎 + 3 个证书透明度日志 + 15 个开放数据集 + 5 个威胁情报
- **信息丰富** — 对已有结果补全 DNS 解析、HTTP 探测、CDN 识别、IP 地理/ASN 信息
- **DNS 爆破** — 高并发词表爆破，递归深度扩展
- **子域置换** — 基于已有子域名生成变异候选（前缀/后缀/数字/连字符插入）
- **存活验证** — HTTP 异步批量检查 / DNS 并发解析（ThreadPool 200 并发）
- **DNS 安全检测** — DNSSEC 状态、多解析器一致性对比（投毒/劫持检测）
- **接管检测** — DNS CNAME + HTTP 指纹双确认，预装 15 种服务指纹
- **代理支持** — 代理优先 → 直连回退，国内外双栈
- **输出格式** — CSV / JSON / TXT

## 快速开始

### 环境要求

- Python 3.14+
- 虚拟环境（推荐）

### 安装

```bash
git clone https://github.com/your/JustOne.git
cd JustOne

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install typer rich requests dnspython loguru aiohttp pydantic tqdm
```

### 配置

复制环境变量模板并根据需要填写 API Key：

```bash
cp config/.env.example config/.env
```

部分模块需要 API Key 才能工作（FOFA、Hunter、Shodan、ZoomEye、VirusTotal 等），不配置则自动跳过。

## 使用

### 完整收集

```bash
# 默认流程：搜索引擎 + 证书 + 数据集 + 爆破 + 置换
python justone.py main example.com

# 跳过特定模块
python justone.py main example.com --no-brute
python justone.py main example.com --no-altdns
python justone.py main example.com --no-search
```

### 子域爆破

```bash
python justone.py brute example.com
python justone.py brute example.com -w wordlist.txt -c 1000
```

### 子域置换扩展

```bash
# 自动收集+爆破后置换
python justone.py altdns example.com

# 从已知子域名文件直接置换
python justone.py altdns example.com -i subdomains.txt

# 禁用特定置换规则
python justone.py altdns example.com -i subs.txt --no-number --no-insert
```

### 存活检查 & DNS 安全检测

```bash
# HTTP 存活检查（默认，aiohttp 异步 100 并发，推荐）
python justone.py check example.com

# DNS 检查（ThreadPool 并发，默认 200 并发）
python justone.py check example.com --dns

# DNS + CDN 识别（支持 CSV/TXT 文件输入）
python justone.py check -i results/collect_example.com.csv --dns --cdn

# 自定义 DNS / CDN 并发数
python justone.py check example.com --dns --cdn -dc 500 -cc 200

# DNS 安全检测（DNSSEC + 投毒/劫持检测）
python justone.py check example.com --dns-security
python justone.py check example.com --dnssec

# 从文件批量检查（支持 CSV 和 TXT 格式）
python justone.py check -i subdomains.txt --dns
python justone.py check -i results/collect_example.com.csv --dns
```

| `check` 参数 | 说明 | 默认值 |
|-------------|------|--------|
| `--dns` | 使用 DNS 解析检查存活（并发） | HTTP 检查 |
| `--cdn` | 执行 CDN 识别 | 关闭 |
| `--dns-security` / `--dnssec` | DNS 安全检测 | 关闭 |
| `-i`, `--input` | 输入文件（支持 CSV / TXT） | — |
| `-dc`, `--dns-concurrent` | DNS 解析并发数 | 200 |
| `-cc`, `--cdn-concurrent` | CDN 识别并发数 | 100 |

### 子域信息丰富

对已有子域名结果进行 DNS 解析、HTTP 探测、CDN 识别和 IP 定位补全：

```bash
# 从 SQLite 数据库读取并丰富
python justone.py enrich results/result.sqlite3

# 指定表名
python justone.py enrich results/result.sqlite3 -t example_com

# 设置并发数
python justone.py enrich results/result.sqlite3 -c 200
```

### 子域接管检测

```bash
python justone.py takeover example.com
python justone.py takeover -i subdomains.txt
python justone.py takeover example.com --concurrent 50
```

### 输出选项

```bash
python justone.py main example.com -o results.csv          # 指定输出路径
python justone.py main example.com -f json                 # 输出格式: csv/json/txt
```

未指定输出路径时，结果自动保存到 `results/` 目录：

| 命令 | 默认文件名 |
|------|-----------|
| `main` | `results/collect_域名.csv` |
| `brute` | `results/brute_域名.csv` |
| `altdns` | `results/altdns_域名.csv` |
| `check` | `results/check_域名.csv` |
| `enrich` | `results/result.sqlite3`（读取已有数据库，原地更新） |
| `takeover` | `results/takeover_域名.csv` |

## 模块架构

```
justone.py          ← Typer CLI 入口
config/
  settings.py       ← Pydantic BaseSettings 配置
  logging.py        ← loguru 日志
common/
  module.py         ← 同步模块基类 (requests)
  async_module.py   ← 异步模块 Mixin (aiohttp)
  domain.py         ← 域名解析
  utils.py          ← 工具函数 (匹配/代理/重试)
  resolve.py        ← DNS 批量解析
  database.py       ← SQLite 持久化
  modules/
    collect.py        ← 收集调度器
    brute.py          ← DNS 爆破
    altdns.py         ← 子域置换
    enrich.py         ← 子域信息丰富（DNS/HTTP/IP 补全）
    export.py         ← CSV/JSON/TXT 导出
  search/           ← 12 个搜索引擎
  certificates/     ← crt.sh / CertSpotter / Censys
  datasets/         ← 15 个开放数据集
  dnsquery/         ← MX / NS / SOA / SPF / TXT 查询
  intelligence/     ← Threat Intelligence (AlienVault / VirusTotal 等)
  check/            ← HTTP / DNS / CDN / AXFR / 安全检测等
  takeover/         ← 子域接管检测
data/               ← 词表、CDN 指纹、公共后缀列表
```

## 代理配置

`config/.env`:

```ini
PROXY_ENABLE=true
PROXY_POOL=http://127.0.0.1:10808,socks5://127.0.0.1:10809
```

**三层代理策略**：

| 层级 | 说明 | 协议 |
|------|------|------|
| HTTP 代理 | 所有 requests / aiohttp 请求走代理 | `http://` |
| DNS 代理 | DNS-over-TCP 走 SOCKS5 绕过 GFW 污染 | `socks5://` / `socks5h://` |
| 浏览器代理 | Playwright（Google/Yahoo）走代理 | `http://` / `socks5://` |

**行为**：配置了代理则**代理优先** → 失败回退直连；代理未运行时自动回退直连 DNS（仅告警一次），不会卡死。

## 测试

```bash
pytest                          # 全量测试
pytest tests/test_altdns.py    # 单模块测试
pytest -k "test_dnssec"         # 按关键字过滤
```

全量测试约 350+ 用例，7 个跳过为 API Key 缺失模块，属正常预期。

## 数据源

每个模块可通过命令行 `--no-xxx` 选择性关闭，或在 `config/.env` 中配置对应的 API Key。

| 类别 | 模块 |
|------|------|
| 搜索引擎 | Baidu, Bing, Google, Yahoo, Yandex, So, Sogou, Fofa, Hunter, Shodan, ZoomEye, GitHub |
| 证书 | crt.sh, CertSpotter, Censys |
| 数据集 | Anubis, Chinaz, Circl, Cloudflare, DNSDumpster, FullHunt, HackerTarget, IP138, LeakIX, NetCraft, PassiveDNS, RapidDNS, Robtex, SecurityTrails |
| 威胁情报 | AlienVault OTX, URLScan.io, ThreatBook, VirusTotal, ThreatMiner |
| DNS 查询 | MX, NS, SOA, SPF, TXT |
| IP 定位 | CDN 识别 / CIDR / ASN / ORG 查询 |
| 安全检测 | DNSSEC / 多解析器一致性 / 劫持检测 |
| 接管检测 | 15 种服务指纹 (GitHub Pages, AWS S3, Heroku, Vercel 等) |
| 信息丰富 | 对已有数据库结果补全 DNS 解析、HTTP 探测、CDN、IP 信息 |

## 致谢

本项目的模块架构和收集思路参考了 [OneForAll](https://github.com/shmilylty/OneForAll) — 一个优秀的子域名收集工具。

