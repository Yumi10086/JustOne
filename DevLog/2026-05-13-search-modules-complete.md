# JustOne 项目开发日志

## 2026-05-13

### 今日完成工作

#### 1. 回顾对话 + Bing/Baidu 代码分析修复 ?

- 读取 DevLog 历史日志，确认之前工作进度 (270 passed, 7 skipped)
- 分析 `modules/search/bing.py` 及引用链路，发现 5 个 bug:
  1. `common/__init__.py` 缺失 → 创建
  2. `begin()`/`finish()` 在模块级 `run()` 中重复调用 → 移除冗余
  3. 请求前未调用 `get_header()` → 添加
  4. `utils.get_logger()` 效率低 → 改为直接 `from config.logging import logger`
  5. `bing_run`/`baidu_run` 死代码
- 修复 bing.py 和 baidu.py 相同问题
- 分析百度无法发现域名的原因（风控严格、site: 支持差）

#### 2. modules/ 全面 Bug 扫描与修复 ?

扫描全部 17 个模块文件，发现并修复 9 个 bug:

| 严重度 | 文件 | Bug | 修复 |
|--------|------|-----|------|
| 严重 | dnsquery/mx.py | DNSResolver 类不存在，导入崩溃 | 改用 `utils.dns_query` |
| 高 | collect.py | `get_results()` 永远返回 `[]` | 改为从 `self.subdomains` 生成 |
| 高 | collect.py | `registered_domain` 可能为 None | 添加 `ValueError` 保护 |
| 中 | certificates/crtsh.py | 模块级 `run()` 重复 begin/finish | 移除冗余调用 |
| 中 | datasets/leakix.py | 同上 | 同上 |
| 低 | export.py | `format` 参数名遮蔽内置函数 | 重命名为 `fmt` |
| 低 | dnsquery/__init__.py | MXQuery 未导出 | 导入并加入 `__all__` |
| 低 | brute.py | 裸 `except Exception: pass` | 改为 `except Exception as e: logger.debug(...)` |
| 低 | check/http.py | 同上 × 3 处 | 同上 |

#### 3. 搜索引擎模块适配（OneForAll → JustOne）?

创建 `common/search.py` Search 基类（继承 Module），补充:
- `check_subdomains()` — 分页控制
- `filter()` — 子域前缀分析
- `recursive_subdomain()` — 递归搜索支持

适配 11 个来自 OneForAll 的搜索模块:

| 类别 | 模块 | API 依赖 |
|------|------|----------|
| API | fofa_api.py | FOFA API Key |
| API | hunter.py | 鹰图 API Key |
| API | shodan_api.py | Shodan API Key |
| API | zoomeye_api.py | ZoomEye 账号 |
| API | github_api.py | GitHub Token |
| Web | google.py | 需代理 |
| API | google_api.py | Google Custom Search API |
| Web | yahoo.py | 需代理 |
| Web | yandex.py | - |
| 抓取 | gitee.py | - |

适配工作:
- 导入路径: `from common.search import Search` / `from config.logging import logger` / `from config import settings`
- `Search.__init__(self)` → `super().__init__(domain, config)`
- `logger.log('ERROR', ...)` → `logger.error(...)`
- `self.module` 改为正确类名
- 模块级 `run(domain)` → `run(domain, config=None) -> Set[str]`
- API Key 映射: `settings.github_api_token` → `settings.github_token`
- `recursive_search` → `self.recursive`
- 安装依赖: beautifulsoup4

注册: `modules/search/__init__.py` + `modules/collect.py` 全部接入收集调度器

#### 4. 代理链路修复 ?

问题: Google/Yahoo 无法访问 → 代理配置未接入运行时

修复:
- `config/settings.py`: 新增 `proxy_pool` 字段 + `get_proxy_list()` 方法
- `config/settings.py`: ConfigManager.http_config 接入 proxy_pool
- `justone.py`: 启动时调用 `utils.set_http_config()` 注入全局代理配置

使用方式:
```env
# config/.env
PROXY_ENABLE=true
PROXY_POOL=http://127.0.0.1:7890
```

#### 5. GitHub Token API 集成 ?

- `github_api.py` 连接 Settings 中的 `github_token`
- 实际运行测试: GitHub API 发现 **51 个子域名**

---

### 测试统计

| 测试集 | 结果 |
|--------|------|
| 全部测试 | **270 passed, 7 skipped** |
| 回归 | 0 个失败 |
| 收集测试 (bilibili.com) | GitHub 51 + LeakIX 27 + Bing 1 = **79 个子域名** |

---

### 修改文件清单

| 文件 | 操作 |
|------|------|
| `common/__init__.py` | 新建 |
| `common/search.py` | 新建 |
| `modules/dnsquery/mx.py` | 修复 DNSResolver 崩溃 |
| `modules/dnsquery/__init__.py` | 导出 MXQuery |
| `modules/collect.py` | 修复 get_results + registered_domain + 注册 11 个新搜索模块 |
| `modules/export.py` | format → fmt |
| `modules/certificates/crtsh.py` | 修复 begin/finish 重复 |
| `modules/datasets/leakix.py` | 修复 begin/finish 重复 |
| `modules/search/bing.py` | 前期修复 (get_logger + get_header + begin/finish) |
| `modules/search/baidu.py` | 同上 |
| `modules/search/__init__.py` | 注册 11 个新模块 |
| `modules/search/fofa_api.py` | OneForAll 适配 |
| `modules/search/hunter.py` | OneForAll 适配 |
| `modules/search/shodan_api.py` | OneForAll 适配 |
| `modules/search/zoomeye_api.py` | OneForAll 适配 |
| `modules/search/github_api.py` | OneForAll 适配 |
| `modules/search/google.py` | OneForAll 适配 |
| `modules/search/google_api.py` | OneForAll 适配 |
| `modules/search/yahoo.py` | OneForAll 适配 |
| `modules/search/yandex.py` | OneForAll 适配 |
| `modules/search/gitee.py` | OneForAll 适配 |
| `modules/brute.py` | 裸 except:pass 修复 (2处) |
| `modules/check/http.py` | 裸 except:pass 修复 (3处) |
| `config/settings.py` | 新增 proxy_pool + censys_api_token |
| `justone.py` | 代理配置注入 + import common.utils |

---

### 待完成任务

- [ ] **解决域名收集模块收集不完全问题**: 当前各搜索模块发现子域名数量偏少，需要排查是否因请求头、延迟、分页逻辑或反爬策略导致收集不完整

---

*更新于: 2026-05-13*
