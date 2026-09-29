# JustOne 项目开发日志

## 2026-06-10 — takeover 存活预检 + CSV 输入修复 + Playwright SOCKS5 DNS 修复

### takeover -i CSV 输入解析修复

**问题**: `takeover -i` 将输入文件每行原文作为子域名，不解析 CSV 多列格式。
当输入为 `check` 命令输出（`subdomain,ip,resolve` 格式）时，整行被当作子域名字符串，
导致 DNS 解析时超过 255 字节限制报错，或返回 NXDOMAIN（实际子域名从未被检测）。

**修复**: `justone.py` takeover 命令的 `-i` 文件读取逻辑:
- 首行含逗号 → 判定为 CSV → 用 csv.reader 解析，提取第一列作为子域名
- 自动跳过表头行（subdomain / domain / host / hostname / url）
- 首行不含逗号 → 维持原有逐行纯文本行为

### takeover 存活预检（DNS A 记录）

**新增**: `takeover` 命令默认在 CNAME 接管检测前执行 DNS A 记录存活预检，
过滤掉 NXDOMAIN 的已死子域名，大幅减少无效 CNAME 查询。

**改动文件**:
| 文件 | 改动 |
|------|------|
| modules/takeover/takeover.py | +`_resolve_a()` 静态方法（带 lru_cache）；`run()` 新增阶段 1 存活预检；`TakeoverCheck.__init__` 新增 `pre_check` 配置项 |
| justone.py | +`--no-pre-check` 参数；统计输出新增存活/已死计数 |

**行为**:
- 默认开启：先并发解析 A 记录，过滤 NXDOMAIN，仅对存活子域名做 CNAME 接管检测
- `--no-pre-check`：跳过预检，回退到旧行为
- 输出示例：`存活预检: 5000 → 320 存活, 4680 已死（跳过接管检测）`

### Playwright SOCKS5 代理 DNS 污染修复

**问题**: Google/Yahoo 模块使用 Playwright 浏览器，代理配置 `socks5://127.0.0.1:10808` 时
Chromium 在本地解析 DNS（`socks5://` 语义），导致 google.com 被 GFW 污染 → 连接超时。
而其他 HTTP 模块（requests/aiohttp）不受影响。

**修复**: `common/utils.py` → `_convert_playwright_proxy()`:
- `socks5://` 自动转为 `socks5h://`（代理端解析 DNS）
- 保留已有 username / password / bypass 等字段
- `http://` 代理不受影响

### 修复文件清单

| 文件 | 改动 |
|------|------|
| justone.py | takeover -i CSV 解析修复；+`--no-pre-check` 参数；统计输出优化 |
| modules/takeover/takeover.py | +`_resolve_a()`；`run()` 存活预检阶段；+logger 导入 |
| common/utils.py | `_convert_playwright_proxy()` socks5 → socks5h 转换 |

### 测试

- test_takeover.py: 39/39 passed
- _convert_playwright_proxy 转换验证：全部用例通过

---

*时间: 2026-06-10*
*状态: 修改完成，待提交*
