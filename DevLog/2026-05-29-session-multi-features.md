# JustOne 项目开发日志

## 2026-05-29 — 子域置换模块 + DNS安全检测 + 代理模式修复

### 一、回顾对话

查看 DevLog/ 历史日志，了解项目当前状态和未完成事项。

### 二、子域置换模块 (altdns)

基于已有子域名，通过 4 种置换规则生成新候选并 DNS 验证：

| 规则 | 示例 |
|------|------|
| prefix (加前缀) | dev-api.example.com |
| suffix (加后缀) | api-dev.example.com |
| number (加数字) | api1~api10.example.com |
| insert (插入连字符) | apidev → api-dev.example.com |

**新文件:**
- modules/altdns.py — Altdns 类，load_wordlist / generate_candidates / resolve_batch
- tests/test_altdns.py — 18 个测试（1 skip）

**修改文件:**
- modules/__init__.py — 注册 Altdns
- justone.py:
  - main 命令新增 --altdns/--no-altdns 标志
  - 新增独立 altdns 命令（支持 -i / --no-prefix 等参数）

### 三、代理模式修复

之前  在构造函数中始终为 None，导致代理配置几乎不生效。

**修改:**
- common/module.py __init__: self.proxy = utils.get_random_proxy() if self.proxy_enable else None
- _do_get / _do_post: 改为代理优先 (attempt 0 proxy, attempt 1 direct)
- async_module.py async_get / async_post: 同样代理优先
- get_proxy() 简化，删除 fetch_url 中的冗余赋值

**AGENTS.md 更新:** 删除旧的 direct-first 说明，改为 proxy-first 说明

### 四、DNS安全检测模块

在 check 命令下新增 --dns-security 标志，执行三项检测：

| 检测项 | 方法 | 状态说明 |
|--------|------|---------|
| DNSSEC | 查询 DS + RRSIG + NSEC | secure / insecure / info |
| 解析一致性 | 对比国内(223.5.5.5/114.114.114.114) vs 国外(8.8.8.8/1.1.1.1) | secure / suspicious |
| 劫持检测 | 查 NS/SOA，对比多解析器 | secure / suspicious |

**新文件:**
- modules/check/dns_security.py — DNSSecurityCheck 类
- tests/test_check_dns_security.py — 13 个测试

**修改文件:**
- modules/check/__init__.py — 注册 DNSSecurityCheck
- justone.py check 命令新增 --dns-security / --dnssec 参数

### 五、文档更新

- README.md — 完整重写，覆盖所有命令模块、架构、配置、测试说明
- requirements.txt — 按核心/可选分类生成
- justone.py 顶部用法说明 — 新增 altdns / takeover / dns-security 示例

### 六、测试结果

全量测试: 340 passed, 8 skipped
比上期 (309 passed, 7 skipped) 新增 31 测试 + 1 skip（altdns 网络测试跳过）

---

*日期: 2026-05-29*
*状态: 完成*
