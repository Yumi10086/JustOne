# JustOne 项目开发日志

## 2026-05-20

### 一、dnsquery 模块适配

从 OneForAll 迁移 4 个 DNS 查询模块并适配为 JustOne `Module` 基类。

| 文件 | 类 | 查询类型 | 适配要点 |
|------|-----|---------|---------|
| `ns.py` | QueryNS | NS 记录 | `common.lookup.Lookup` → `common.module.Module` |
| `soa.py` | QuerySOA | SOA 记录 | 添加 `Optional, Set` 类型标注 |
| `spf.py` | QuerySPF | SPF 记录 | 移除 `save_json()`/`gen_result()`/`save_db()` 等 O4A 遗留调用 |
| `txt.py` | QueryTXT | TXT 记录 | 直接使用 `utils.dns_query()` 查询 DNS 记录 |

**集成**：`collect.py` 新增 `_init_dnsquery_modules()` / `_run_dnsquery_modules()` 方法，所有 5 个 DNS 模块（含已有的 MXQuery）加入收集流程。

---

### 二、Bug 修复

#### 2.1 数据集模块 Bug

| 文件 | 行号 | 问题 | 修复 |
|------|------|------|------|
| `fullhunt.py` | `:41` | **缺少 `have_api()` 检查**，API key 为空时仍发请求 | 在 `run()` 开头添加 `have_api(self.api)` 检查 |
| `robtex.py` | `:48` | **`self.subdomains =` 覆盖赋值**，循环内每次覆盖前次结果 | 改为 `self.collect_subdomains(resp)`（内部已调用 `update`） |

#### 2.2 SPF 模块 Bug

| 文件 | 问题 | 修复 |
|------|------|------|
| `spf.py` | 查询 `'SPF'` 记录类型始终返回 None（RFC 7208 已废弃 SPF 独立 RR 类型） | 改为查询 `'TXT'` 并过滤 `v=spf1` 前缀 |

验证：google.com → 发现 `_spf.google.com`，qq.com → 发现 `spf.mail.qq.com`。

#### 2.3 服务端问题模块（添加警告提示）

| 文件 | 根因 | 修复 |
|------|------|------|
| `anubis.py` | API 返回 403（Cloudflare 防护） | 添加 `check=False` + 状态码检查警告 |
| `dnsdumpster.py` | CSRF token 获取失败 | **完全重写**（见第四节） |
| `netcraft.py` | 返回 403（拦截自动化访问） | 添加 `check=False` + 状态码检查警告 |
| `sitedossier.py` | HTTP 连接失败 | 添加 `check=False` + 状态码检查警告 |
| `cebaidu.py` | ce.baidu.com 已停止服务（HTTPS SSL EOF + HTTP 503） | 添加 HTTPS→HTTP 降级 + 明确警告提示 |

---

### 三、ZoomEye API v1 → v2 升级

| 项目 | 旧 (v1) | 新 (v2) |
|------|---------|---------|
| 端点 | `GET /web/search` | `POST /v2/search` |
| 查询格式 | URL 参数 `query=hostname:domain` | JSON body `qbase64`（Base64 编码） |
| 认证 | JWT 登录 + API-KEY 双模式 | 仅 `API-KEY` header |
| 分页 | `page` 参数 | `page` + `pagesize`（最大 10000） |
| 响应格式 | `{"matches": [...]}` | `{"code": 60000, "data": [...]}` |

**代码改动**：
- 删除 JWT 登录逻辑（`_get_auth_token`、`_jwt_login`）
- 查询语句 base64 编码后通过 POST JSON body 发送
- 新增 `402`（额度不足）、`422`（参数错误）状态码处理
- 从非 200 响应中提取 JSON 错误消息
- `have_api` 简化为仅检查 `self.api_key`

---

### 四、DNSDumpster 模块重写

**旧版问题**：访问 dnsdumpster.com 首页获取 CSRF token → 站点不返回 cookie，POST 失败

**新版方案**：
| 项目 | 旧 | 新 |
|------|-----|-----|
| 端点 | `https://dnsdumpster.com/` (GET + POST 表单) | `https://api.dnsdumpster.com/domain/{domain}` |
| 认证 | CSRF token | `X-API-Key` header |
| 速率限制 | 无 | 3s 延迟（API 限制 1 请求/2 秒） |
| 响应解析 | HTML 正则匹配 | JSON: `a`/`cname`/`ns`/`mx` 字段提取 |

**配置新增**：
- `settings.py`: `dnsdumpster_api_key` 字段
- `.env.example`: `DNSDUMPSTER_API_KEY`

---

### 五、API 配置补齐

`config/.env.example` 新增 **20 个** API 配置项，与 `settings.py` 全部 34 个 API 字段完全对齐：

| 模块使用 | 预留字段 |
|----------|---------|
| `CHINAZ_API`, `SECURITYTRAILS_API`, `CIRCL_USERNAME/PASSWORD`, `DNSDB_API_KEY`, `IPV4INFO_API_KEY`, `PASSIVEDNS_ADDR/TOKEN`, `CLOUDFLARE_API_TOKEN`, `SPYSE_API_TOKEN`, `DNSDUMPSTER_API_KEY` | `BING_API_ID/KEY`, `RISKIQ_USERNAME/API_KEY`, `THREATBOOK_API_KEY`, `HACKERTARGET_API_KEY`, `GOOGLE_API_ID/KEY` |

---

### 六、测试结果

**270 passed, 7 skipped, 0 failed**

---

*日期: 2026-05-20*
*状态: Bug 修复 + API 升级 + 配置补齐完成，零回归*
