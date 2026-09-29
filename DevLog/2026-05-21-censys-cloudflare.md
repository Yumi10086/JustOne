# JustOne 项目开发日志

## 2026-05-21

### 一、新增 Censys 证书查询模块

#### 1.1 新建 `modules/certificates/censys.py`

通过 Censys API v2 查询证书透明度日志中与目标域名关联的 SSL/TLS 证书，从证书 `names` 字段提取子域名。

| 项目 | 说明 |
|------|------|
| 类 | `Censys` |
| 端点 | `POST https://search.censys.io/api/v2/certificates/search` |
| 认证 | `Authorization: Bearer <token>`（使用 `CENSYS_API_TOKEN`） |
| 查询 | `names: {domain}` |
| 分页 | cursor 分页，最多 3 页，每页 100 条 |
| 跳过 | `have_api()` 检查，Token 未配置时自动跳过 |

#### 1.2 集成注册

- `modules/certificates/__init__.py` — 导入并导出 `Censys` / `censys_run`
- `modules/collect.py:117` — `_init_certificate_modules()` 中添加 `Censys` 实例化

---

### 二、重写 Cloudflare API 模块

#### 2.1 第一轮重写（移除危险操作、修复认证）

| 项目 | 旧 | 新 |
|------|-----|-----|
| 认证方式 | `__init__` 中设一次 header，`get_header()` 调用后会覆盖 | 每次请求前调用 `_set_auth_header()` 重新设置 |
| 账户发现 | 仅查 `GET /accounts` 列表 | 优先用 `CLOUDFLARE_ID` 直接调用 `GET /accounts/:id/tokens/verify` |
| Zone 创建 | 未找到 Zone 时自动创建（无清理） | **已移除** |
| DNS 分页 | `per_page=10`，递归等待 5 秒 | `per_page=100`，标准分页遍历 |
| Token 验证 | 无 | 调用 `/accounts/:id/tokens/verify` 验证有效性 |
| DNS 记录提取 | 仅用 `match_subdomains` 匹配响应文本 | 同时提取 `name` 和 `content` 字段 |

`.env.example` 修复：`CLOUDFLARE_API_TOKEN` 重复两次 → 合并。

#### 2.2 第二轮重写（参考原始 OneForAll 代码）

根据用户提供的原始 OneForAll 参考代码，恢复 Zone 创建 + 清理机制：

| 特性 | 说明 |
|------|------|
| `get_account_id()` | 独立方法，通过 `GET /accounts` 列表获取账户 ID |
| `get_or_create_zone()` | 已有 Zone 直接返回，不存在则调用 `create_zone()` |
| `create_zone()` | 使用 `jump_start: True` 创建临时 Zone 触发 Cloudflare DNS 自动扫描 |
| `cleanup()` | 在 `finally` 块中删除临时创建的 Zone，已有 Zone 不动 |
| `list_dns()` | 最多 6 次重试（每次等 5 秒），适应新 Zone 扫描延迟，找到记录后提前退出 |
| `run()` | `try/except/finally` 确保异常时也能清理临时 Zone |

#### 2.3 第三轮精简（移除 cloudflare_id 依赖）

- 移除 `CLOUDFLARE_ID` 分支逻辑，统一通过 `GET /accounts` 列表获取账户 ID
- 与参考代码一致，只需 `CLOUDFLARE_API_TOKEN`

---

### 测试结果

**270 passed, 7 skipped, 0 failed**（零回归，三轮修改均通过）

---

*日期: 2026-05-21*
*状态: 新增 Censys 证书模块 + Cloudflare API 模块三轮重写完成，零回归*
