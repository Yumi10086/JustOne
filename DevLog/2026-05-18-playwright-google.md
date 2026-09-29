# JustOne 项目开发日志

## 2026-05-18

### 一、Hunter API 修复 — base64url 编码

根据 Hunter 最新 API 文档修复 `modules/search/hunter.py`：

| 项目 | 旧 | 新 |
|------|-----|-----|
| search 编码 | 原始字符串 | RFC 4648 `base64.urlsafe_b64encode()` |
| is_web | 1（仅 Web） | 3（全部资产） |
| 429 限流 | 直接报错退出 | 等待 10 秒自动重试 |
| records 类型安全 | 直接遍历 | `isinstance(records, list)` 保护 |

参考文档: https://hunter.qianxin.com/home/helpCenter?type=api

---

### 二、.env.example 同步更新

对比 `.env`、`settings.py` 和 `.env.example`，发现 4 个缺失字段并补充：

| 新增字段 | 说明 |
|---------|------|
| `CENSYS_API_TOKEN` | Censys API（.env 实际使用此字段） |
| `GOOGLE_API_ID` | Google Custom Search |
| `GOOGLE_API_KEY` | Google Custom Search |
| `ZOOMEYE_API` | ZoomEye 新版 API-KEY 认证（zoomeye_api.py 优先使用） |

---

### 三、Playwright Google 搜索模块 — 设计阶段

**目标**：用 Playwright 异步 API 恢复 Google Web 搜索（5月13日因浏览器级反爬注销）。

**方案**: A+B 结合 — 异步 Playwright 工具模块 + 异步 Google 模块 + 零侵入 Collect 调度器。

**设计文档**: `docs/superpowers/specs/2026-05-18-playwright-google-design.md`

**架构**:
1. `common/playwright_utils.py` — 新建异步页面抓取工具：`fetch_page_html()`、`new_browser_context()`
2. `modules/search/google.py` — 异步重写，`asyncio.run()` 桥接同步 `run()` 入口
3. `modules/search/__init__.py` — 恢复 Google 导出
4. `modules/collect.py` — 恢复 Google 导入，现有调度逻辑不变

**状态**: 设计已确认，待实现。

---

### 四、修改文件清单

| 文件 | 操作 |
|------|------|
| `modules/search/hunter.py` | 已修改 — base64url 编码 + 429 重试 |
| `config/.env.example` | 已修改 — 补充 4 个缺失字段 |
| `docs/superpowers/specs/2026-05-18-playwright-google-design.md` | 已新建 — 设计文档 |

---

*更新于: 2026-05-18*
### 五、待完成任务

- [x] 实现 Playwright 工具函数 — 集成到 `common/utils.py`（~~`common/playwright_utils.py`~~）
- [x] 重写 `modules/search/google.py` — 用 Playwright 异步替换 requests
- [x] 恢复 `modules/search/__init__.py` — 添加 Google 导出
- [x] 恢复 `modules/collect.py` — 添加 Google 模块导入
- [x] 运行测试验证所有模块无回归（270 passed）
### 六、Playwright Google 模块实现（2026-05-18 晚间）

**实现方案调整**：放弃新建 `common/playwright_utils.py`，工具函数直接集成到 `common/utils.py` 末尾。

#### 已完成

| 文件 | 操作 | 说明 |
|------|------|------|
| `common/utils.py` | 新增 3 个函数 | `new_browser_context()`、`fetch_page_html()`、`_convert_playwright_proxy()` |
| `modules/search/google.py` | 完全重写 | requests → Playwright 异步，`asyncio.run()` 桥接同步 `run()` |
| `modules/search/__init__.py` | 修改 | 恢复 `Google` 和 `google_run` 导出 |
| `modules/collect.py` | 修改 | 恢复 `Google` 模块导入和实例化 |

#### 架构设计

```
asyncio.run(_search_all())
  ├── new_browser_context() → (browser, context, pw)
  ├── 首页导航 + consent 弹窗处理
  ├── _search_pages(): 主搜索 + 过滤搜索 + 递归搜索（共用 context）
  ├── browser.close()
  └── pw.stop()  ← 关键：避免 ProactorEventLoop 清理竞争
```

- 单次 `asyncio.run()` 管理完整生命周期，多阶段共用同一 browser context（Cookie 自动保持）
- `pw.stop()` 确保 Playwright Node.js driver 在事件循环关闭前释放子进程

#### 遇到的问题

| 问题 | 原因 | 修复 |
|------|------|------|
| `chrome-headless-shell.exe` 不存在 | Playwright 未安装 Chromium（下载被 GFW 阻断） | `channel="chrome"` 使用系统已有 Chrome |
| `I/O operation on closed pipe` (×3) | `new_browser_context()` 创建了 `pw` 但未调用 `pw.stop()`，subprocess transport 在事件循环关闭后才被 GC 触发 `__del__` | 返回 `pw` 并调用 `pw.stop()` |
| Google 返回 captcha | headless Chrome 被识别为爬虫 | 增强反检测脚本（`chrome.runtime`、permissions query 覆盖、`hardwareConcurrency` 等） |

#### Web/API 模块区分

| 模块 | 类 | source | 说明 |
|------|-----|--------|------|
| Google Web | `Google` | `google.com/web` | Playwright 浏览器抓取 |
| Google API | `GoogleAPI` | `google.com/api` | Google Custom Search JSON API |

---
*更新于: 2026-05-18 晚间*

### 七、待验证 / 待完成任务

- [ ] 验证 `pw.stop()` 后 proactor 警告在生产环境完全消除
- [ ] 验证 Google Web 模块在有代理环境下是否仍触发 captcha
- [ ] 验证 GoogleAPI（`google.com/api`）模块日志显示正确
- [ ] 评估是否需要关闭 headless 模式以提升反检测效果
- [ ] 考虑为 Playwright 下载提供国内镜像脚本（`PLAYWRIGHT_DOWNLOAD_HOST`）
- [ ] 测试 `justone.py` 全流程（含 Google Web + API 双模块）
