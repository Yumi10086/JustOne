# JustOne 项目开发日志

## 2026-05-19

### 一、删除 google_api 模块

`google.com/api` 返回 0 结果、耗时 0.0 秒的根因：`GOOGLE_API_ID` / `GOOGLE_API_KEY` 未在 `.env` 中配置，`have_api()` 检查失败后 `run()` 直接返回空集合。

| 文件 | 变更 |
|------|------|
| `modules/search/google_api.py` | 删除 |
| `modules/search/__init__.py` | 移除 GoogleAPI 导入和导出 |
| `modules/collect.py` | 移除 GoogleAPI 导入和实例化 |
| `config/.env.example` | 移除 GOOGLE_API_ID / GOOGLE_API_KEY 字段 |

`google.com/web`（Playwright 抓取版）不受影响。

---

### 二、certificates / datasets / check 模块适配

从 OneForAll 迁移 modules 并适配为 JustOne `Module` 基类。

#### 2.1 基类增强

- `common/module.py`: 新增 `to_check(filenames)` 方法 —— 检查站点根目录文件（如 robots.txt、sitemap.xml）从中匹配子域名

#### 2.2 certificates（2 个模块）

| 文件 | 类 | 说明 |
|------|------|------|
| `crtsh.py` | Crtsh | 已有（之前已适配） |
| `certspotter.py` | CertSpotter | 从 OneForAll Query → Module 适配 |

#### 2.3 datasets（23 个模块，删 1 个）

| 文件 | 类 | 是否需要 API |
|------|------|-------------|
| `anubis.py` | Anubis | 否 |
| `binaryedge_api.py` | BinaryEdgeAPI | 是 |
| `cebaidu.py` | CeBaidu | 否 |
| `chinaz_api.py` | ChinazAPI | 是 |
| `chinaz.py` | Chinaz | 否 |
| `circl_api.py` | CirclAPI | 是（用户名+密码） |
| `cloudflare_api.py` | CloudFlareAPI | 是 |
| `dnsdb_api.py` | DNSdbAPI | 是 |
| `dnsdumpster.py` | DNSDumpster | 否 |
| `fullhunt.py` | FullHuntAPI | 是 |
| `hackertarget.py` | HackerTarget | 否 |
| `ip138.py` | IP138 | 否 |
| `ipv4info_api.py` | IPv4InfoAPI | 是 |
| `leakix.py` | LeakIX | 已有（之前已适配） |
| `netcraft.py` | NetCraft | 否 |
| `passivedns_api.py` | PassiveDnsAPI | 条件 |
| `qianxun.py` | QianXun | 否 |
| `rapiddns.py` | RapidDNS | 否 |
| `riddler.py` | Riddler | 否 |
| `robtex.py` | Robtex | 否 |
| `securitytrails_api.py` | SecurityTrailsAPI | 是 |
| `sitedossier.py` | SiteDossier | 否 |
| `spyse_api.py` | SpyseAPI | 是 |
| ~~`sublist3r.py`~~ | — | **已删除**（依赖外部 sublist3r 库） |

适配规则：
- `from common.query import Query` → `from common.module import Module`
- `Query.__init__(self)` → `super().__init__(domain, config)`
- 新增类型标注 `Optional, Set`
- `run(domain)` → `run(domain, config=None) -> Set[str]`
- 修复 settings 字段名：`circl_api_username` → `circl_username`、`passivedns_api_addr` → `passivedns_addr`

#### 2.4 check（10 个模块）

| 文件 | 类 | 用途 |
|------|------|------|
| `dns.py` | DNSCheck | DNS 解析验证（已有） |
| `http.py` | HTTPCheck | HTTP 存活检查（已有） |
| `axfr.py` | AXFR | DNS 域传送发现 |
| `cdx.py` | CrossDomain | crossdomain.xml 发现 |
| `cert.py` | CertInfo | SSL 证书发现 |
| `csp.py` | CSP | Content-Security-Policy 发现 |
| `nsec.py` | NSEC | DNSSEC NSEC walking |
| `robots.py` | Robots | robots.txt 发现 |
| `sitemap.py` | Sitemap | sitemap.xml 发现 |
| `cdn.py` | CDNCheck | **新建** CDN 识别 |

适配规则：`from common.check import Check` → `from common.module import Module`，其余同上。

**check 模块不参与 main 收集流程**，仅在 `check` 命令中使用。

---

### 三、CDN 识别模块（新建）

`modules/check/cdn.py` — 通过 209 条 CNAME 关键字 + 540 条 IP CIDR 地址段识别 CDN。

检测方法:
- **CNAME 匹配**: DNS CNAME 记录中包含已知 CDN 特征关键字（Cloudflare、Akamai、阿里云等），返回 CDN 提供商名称
- **IP CIDR 匹配**: 解析 IP 落在已知 CDN 地址段内

使用方式: `python justone.py check example.com --cdn`

---

### 四、check 命令集成

`justone.py check` 命令增强——指定目标域名时：
1. 先执行 6 个发现模块（SSL证书、robots.txt、sitemap、crossdomain.xml、DNS域传送、DNSSEC）
2. 合并发现结果
3. DNS/HTTP 存活验证
4. `--cdn` 选项：CDN 识别

`-i` 文件输入模式保持不变。

---

### 五、模块注册汇总

| __init__.py | 模块数 |
|------------|--------|
| `modules/search/` | 10（减少 1：移除 GoogleAPI） |
| `modules/certificates/` | 2（+1：CertSpotter） |
| `modules/datasets/` | 23（+22：全部 OneForAll 数据集） |
| `modules/check/` | 10（+8：7 个适配 + 1 个新建 CDN） |

所有新增模块已在 `collect.py` 中注册，API key 缺失的模块通过 `have_api()` 自动跳过。

---

### 六、settngs 字段修复

| 文件 | 错误字段 | 正确字段 |
|------|---------|---------|
| `circl_api.py` | `settings.circl_api_username` | `settings.circl_username` |
| `circl_api.py` | `settings.circl_api_password` | `settings.circl_password` |
| `passivedns_api.py` | `settings.passivedns_api_addr` | `settings.passivedns_addr` |
| `passivedns_api.py` | `settings.passivedns_api_token` | `settings.passivedns_token` |

---

### 七、测试统计

**270 passed, 7 skipped, 0 failed**

---

*日期: 2026-05-19*
*状态: 模块适配完成，零回归*
