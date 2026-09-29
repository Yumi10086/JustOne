# Playwright 异步 Google 搜索模块设计

## 背景

Google Web 搜索模块因浏览器级反爬（TLS 指纹检测、HTTP2 要求）已于 5月13日从 `collect.py` 和 `search/__init__.py` 中注销。Playwright 已在 venv 中安装（v1.59.0），需要用它恢复 Google Web 搜索。

## 目标

用 Playwright 异步 API 重写 Google 搜索模块，通过可复用工具模块隔离浏览器逻辑，不侵入其他 11 个同步模块。

---

## 1. `common/playwright_utils.py` — 异步页面抓取工具

### 职责

封装 Playwright 浏览器启动、页面导航、渲染等待、HTML 提取，对外暴露简洁的异步函数。

### 接口

```python
async def fetch_page_html(url, *, proxy=None, timeout=30, wait_until="networkidle") -> str | None
async def new_browser_context(*, proxy=None, user_agent=None) -> (playwright.Browser, playwright.BrowserContext)
```

- `fetch_page_html`：单次页面抓取，自动 launch→navigate→获取 HTML→close，适合一次性的独立请求
- `new_browser_context`：创建浏览器和上下文并返回，调用方自行管理 page 导航和关闭，适合需要保持 Cookie 的多次请求场景
- Chromium headless 启动（`channel="chromium"`）
- 支持 `proxy` 传入 Playwright proxy 格式 `{"server": "http://..."}`
- `wait_until` 默认 `"networkidle"` 确保 JS 渲染完成
- `fetch_page_html` 每次调用独立启动/关闭浏览器；`new_browser_context` 由调用方控制生命周期

### 错误处理

- 浏览器启动失败 → log error，返回 `None`
- 导航超时 → log warning，返回当前 HTML（即使未完成渲染）
- 页面崩溃 → log error，返回 `None`

### 依赖

- `playwright.async_api`
- `config.logging.logger`

---

## 2. `modules/search/google.py` — 异步重写

### 保持不变的部分

- 继承 `common.search.Search` → `common.module.Module`
- 类属性：`module='Google'`, `source='google.com'`
- 工具方法：`_is_blocked()`（逻辑保留，适配 Playwright 返回的 HTML）
- 结果收集：`self.subdomains`、`save_json()`、`gen_result()`、`save_db()`
- `run()` 同步入口签名不变

### 变更

| 项 | 旧（requests） | 新（Playwright） |
|---|---------------|-----------------|
| 发起请求 | `self.get(url, params)` | `await fetch_page_html(url, proxy=proxy)` |
| 首页访问 | `self.get(self.init)` | Playwright 导航 `google.com`，处理 consent 弹窗 |
| Cookie 传递 | `self.cookie = resp.cookies` | Playwright 自动管理 cookie（同一 browser context） |
| 反爬检测 | `_is_blocked(resp)` | `_is_blocked(html_text)`，关键词不变 |
| 子域匹配 | `self.match_subdomains(resp)` | `self.match_subdomains(html_text)`，传 HTML 字符串 |
| 超时 | `self.timeout` (requests) | Playwright `timeout` 参数，独立设置 |

### search_async() 流程

Google 模块使用 `new_browser_context()` 创建浏览器（非 `fetch_page_html`），在同一个 context 内完成所有分页请求以维持 Cookie。

```
1. browser, context = await new_browser_context(proxy=proxy)
2. page = await context.new_page()
3. 访问 google.com 首页 → 获取 cookie / 处理 consent
   - 如果有 consent 弹窗 ("Accept all" 按钮)，点击关闭
4. 构建搜索 URL: https://www.google.com/search?q=site:{domain}&start={page}&num=50&hl=en
5. 导航到搜索页
6. 等待 selector: "#search" 或 "#res"
7. html = await page.content()
8. _is_blocked(html) → 终止
9. match_subdomains(html) → 收集子域名
10. 解析是否有下一页（html 中找 `start=` 链接或 `#pnnext`）
11. 有下一页 → page_num += 50 → 回到步骤 4
12. 结束 → await browser.close()

### run() 同步桥接

```python
def run(self) -> Set[str]:
    if not self.have_api(True):  # Google 不需要 API key，改为传 True
        return self.subdomains
    self.begin()
    asyncio.run(self.search_async())
    self.finish()
    self.save_json()
    self.gen_result()
    self.save_db()
    return self.subdomains
```

### 代理适配

`common/utils.py` 的 `get_random_proxy()` 返回 dict 格式 `{"http": "...", "https": "..."}`。Playwright 需要 `{"server": "http://..."}` 格式。在 Google 模块内做转换，或 `fetch_page_html` 自动处理。

---

## 3. 调度器适配 — `modules/collect.py`

### 零侵入策略

Google 模块的 `run()` 仍然是同步方法（内部 `asyncio.run()`），对 Collect 调度器完全透明。

```python
# collect.py 现有逻辑不变：
thread = threading.Thread(target=_run, daemon=True)
thread.start()
thread.join(timeout=self.module_timeout)
```

唯一变化：在 `_init_search_modules()` 中取消对 Google 的注释，添加导入。

### modules/search/__init__.py

恢复 Google 导出：
```python
from .google import Google, run as google_run
```

---

## 4. 防封策略

| 措施 | 说明 |
|------|------|
| Cookie/Consent 处理 | 首次访问首页，点击 "Accept all" 消除 consent 弹窗 |
| 随机延迟 | `asyncio.sleep(random.uniform(3, 7))` 每次请求之间 |
| 请求头模拟 | Playwright 自带真实 Chrome 指纹（TLS/HTTP2），不做额外伪装 |
| `_is_blocked()` | 保留原有关键词检测：captcha, unusual traffic, sorry, automated queries, "i'm not a robot", verify you are human |
| 状态码回退 | 对 302/301 → 检测重定向目标，若指向 captcha 则终止 |

---

## 5. 修改文件清单

| 文件 | 操作 |
|------|------|
| `common/playwright_utils.py` | **新建** — 异步页面抓取工具 |
| `modules/search/google.py` | **重写** — 用 Playwright 异步替换 requests |
| `modules/search/__init__.py` | **修改** — 恢复 Google 导出 |
| `modules/collect.py` | **修改** — 恢复 Google 模块导入 |

---

## 6. 风险

- **Playwright 启动开销**：每次模块执行需启动浏览器（~1-2s），比 requests 慢，但 Google 搜索本身已是秒级操作
- **Google 反爬升级**：如果 Google 对 headless 浏览器做额外检测，需追加反检测措施（如 `--disable-blink-features=AutomationControlled` 参数）
- **内存**：Chromium ~200MB，单次运行后释放，不累积

---

*草稿: 2026-05-18*
