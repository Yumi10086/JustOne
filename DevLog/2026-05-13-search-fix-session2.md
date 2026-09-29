# JustOne 项目开发日志

## 2026-05-13 (第二轮)

### 一、收集模块 Bug 修复（P0/P1）

#### 1. 分页逻辑 bug — `check_subdomains()` 始终返回 False
- **文件**: `common/search.py:28-32`
- **根因**: `search_enable_full_search` 默认为 False 时，`check_subdomains()` 返回 False，导致所有 Search 子类只爬第 1 页
- **影响**: Google, Yahoo, Yandex, Gitee, GoogleAPI
- **修复**: 移除冗余开关，有结果即继续分页

#### 2. Gitee BeautifulSoup + fuzzy=False 导致 0 结果
- **文件**: `modules/search/gitee.py:48`
- **根因**: BeautifulSoup 传给 `match_subdomains()` 后 `.text` 剥离 HTML 标记，`fuzzy=False` 正则依赖 HTML 边界符无法匹配
- **修复**: 移除 BeautifulSoup 包装，直接传 resp，改为 `fuzzy=True`

#### 3. Gitee 页面已改为 JS SPA（后续发现）→ 移除
- **根因**: Gitee 搜索页完全改为 JS 渲染（`<body data-bs-theme="light"></body>` 空壳），requests 无法执行 JavaScript
- **操作**: 从 `search/__init__.py` 和 `collect.py` 中注销 Gitee
- **文件**: `modules/search/__init__.py`, `modules/collect.py`

#### 4. 模块超时从 5s → 27s + Thread 超时保护
- **文件**: `common/module.py:18`, `modules/collect.py:154`
- **根因**: `module.http_config['timeout'] = 5` 在代理下过短；且 `module_timeout` 从未被强制执行
- **修复**: 默认超时改为 27s；`_run_module()` 改用 `threading.Thread + join(timeout)` 实现超时保护

---

### 二、Bing/Baidu 反爬虫加固

#### 5. 更新 User-Agent 和默认请求头
- **文件**: `common/utils.py:27-50`
- **变更**:
  - UA 从 Chrome 76 / Firefox 68 (2019) → Chrome 135 / Firefox 137
  - 移除过时头部: DNT, X-Forwarded-For
  - 新增现代头部: Sec-Fetch-Dest, Sec-Fetch-Mode, Sec-Fetch-Site

#### 6. Bing 反爬虫强化
- **文件**: `modules/search/bing.py`
- **变更**:
  - 先访问 Bing 首页获取 Cookie
  - 添加现代请求头 (Referer, Accept-Language, Sec-Fetch-*)
  - `_is_blocked()` 检测 captcha/verify/状态码/b_algo
  - `random.uniform(3, 6)` 随机延迟
  - 过滤 `2f` URL 编码残留

#### 7. Baidu 反爬虫强化
- **文件**: `modules/search/baidu.py`
- **变更**: 同上模式 + 百度专用反爬关键词（IP异常、验证码等）+ `random.uniform(2, 5)`

---

### 三、API 模块修复

#### 8. FOFA API 修复
- **文件**: `modules/search/fofa_api.py`
- **变更**:
  - `fields='host'` 限定返回字段
  - `max_page=100` 防死循环
  - `_handle_api_error()` 检测 JSON `error:true` 字段（FOFA HTTP 200 也会返回错误）
  - 从 `results[i][0]` 直接提取 host 不再正则匹配整个响应
- **状态**: API 可用，但账户 F 点余额不足

#### 9. Hunter API 修复（P0 致命 Bug）
- **文件**: `modules/search/hunter.py`
- **变更**:
  - 移除 base64 编码（Hunter 需要原始查询字符串 `domain.suffix="..."`）
  - `domain_suffix` → `domain.suffix`（下划线改点语法）
  - `total` 空值保护 `or 0`
  - `_handle_api_error()` 检测 JSON `code != 200`
  - 从 `data.arr[].domain` 直接提取
- **状态**: API 可用，但 Key 已过期

#### 10. Shodan API 重写
- **文件**: `modules/search/shodan_api.py`
- **变更**:
  - 使用官方 `shodan` 库替代原始 HTTP 请求
  - `api.dns.domain_info()` — DNS 子域枚举
  - `api.search('hostname:.{domain}')` — 全量搜索，最多 10 页
  - 代理通过 `shodan.Shodan(key, proxies=...)` 传入
  - `shodan.APIError` 异常处理
- **状态**: API 可用，但未配置 Key

#### 11. ZoomEye API 适配新认证
- **文件**: `modules/search/zoomeye_api.py`
- **变更**:
  - 新版 `API-KEY` header 认证（JWT 登录已弃用）
  - 登录移到 `run()` 一次执行，token 传入 `search()` 复用
  - 403/401/429 状态码检查移到循环开头
  - 从 `matches[].site/hostname` 直接提取
- **状态**: 旧 JWT API 已弃用，需使用 `ZOOMEYE_API` 环境变量

---

### 四、搜索引擎模块统一修复

#### 12. `site:.` 点前缀语法错误（P0）
- **影响**: Yahoo, Yandex, Google, GoogleAPI
- **根因**: `site:.' + domain` 产生 `site:.example.com`，搜索语法不正确
- **修复**: 全部改为 `site:` + domain

#### 13. `fuzzy=False` 统一改为 `fuzzy=True`（P0）
- **影响**: Gitee, Yahoo, Yandex, Google
- **根因**: `fuzzy=False` 正则依赖 HTML 边界符（`>`, `"`, `'`），搜索引擎页面结构不满足
- **修复**: 全部改为 `fuzzy=True`

#### 14. 反爬检测 `_is_blocked()` 误报修复
- **根因**: `'robot'` 关键词匹配了 Google CSS 中的 `Roboto` 字体名
- **影响**: Google, Yahoo, Yandex
- **修复**: 改为精确短语 `'not a robot'` / `"i'm not a robot"`

#### 15. URL 编码 `2f` 过滤器大小写 Bug
- **影响**: Bing, Baidu, Yahoo, Google, Yandex（全部 5 模块）
- **根因**: `s.startswith('2F')` 只匹配大写，实际为小写 `2f`
- **修复**: 全部改为 `s.lower().startswith('2f')`

#### 16. 代理格式错误（关键 Bug）
- **文件**: `common/utils.py:133`
- **根因**: `get_random_proxy()` 返回原始字符串 `'http://127.0.0.1:7890'`，requests 需要 dict 格式 `{'http': '...', 'https': '...'}`
- **修复**: 字符串自动转为 dict

#### 17. 持久化 Session
- **文件**: `common/module.py`
- **变更**: `get()/post()/head()/delete()` 从每次 `requests.Session()` 改为复用 `self._get_session()`
- **效果**: Cookie 在请求间正确保持

---

### 五、模块移除

#### 18. Gitee 移除 — JS SPA，requests 不可用
- **文件**: `modules/search/__init__.py`, `modules/collect.py`

#### 19. Google Web 移除 — 浏览器级反爬，需 TLS 指纹/HTTP2
- **文件**: `modules/search/__init__.py`, `modules/collect.py`

---

### 六、测试统计

| 测试集 | 结果 |
|--------|------|
| 全部测试 | **270 passed, 7 skipped** |
| 回归 | 0 个失败 |

### 七、修改文件清单

| 文件 | 操作 |
|------|------|
| `common/module.py` | 持久化 Session + 超时 5→27 + http_config 更新 |
| `common/utils.py` | UA 升级 + 默认头 + 代理格式修复 |
| `common/search.py` | `check_subdomains()` 分页修复 |
| `modules/collect.py` | Thread 超时保护 + 移除 Gitee/Google |
| `modules/search/__init__.py` | 移除 Gitee/Google |
| `modules/search/bing.py` | 反爬虫加固 |
| `modules/search/baidu.py` | 反爬虫加固 |
| `modules/search/gitee.py` | 反爬加固 + 最终废弃 |
| `modules/search/yahoo.py` | site:.→site: + fuzzy=True + 反爬 + 2F 过滤 |
| `modules/search/yandex.py` | site:.→site: + fuzzy=True + 反爬 + 重定向 + 2F 过滤 |
| `modules/search/google.py` | site:.→site: + fuzzy=True + 反爬 + 2F 过滤 + 最终废弃 |
| `modules/search/google_api.py` | site:.→site: + 错误处理 + 随机延迟 |
| `modules/search/fofa_api.py` | fields=host + JSON error 检测 + max_page |
| `modules/search/hunter.py` | base64→原始字符串 + 语法修复 + error 检测 |
| `modules/search/shodan_api.py` | 官方 shodan 库重写 |
| `modules/search/zoomeye_api.py` | API-KEY 认证 + 登录复用 |
| `tests/test_module.py` | timeout 断言 5→27 |

### 八、待完成任务

- [ ] 配置 FOFA / Hunter / Shodan / ZoomEye API Key 后可正常使用
- [ ] Google Web 和 Gitee 需要无头浏览器方案（Playwright）才能恢复

---

*更新于: 2026-05-13*
