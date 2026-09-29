# JustOne 项目开发日志

## 2026-05-26 — 异步收集架构设计 → 完成

### 一、背景

根据 JustOne构想.md §9 异步架构设计 + JustOne项目实现指导.md Phase 5 规划，
当前 Collect 调度器使用 threading.Thread 串行执行 39 个模块，max_concurrent=50 为死代码。
需要改造为 asyncio 驱动的并发调度器。

### 二、设计决策

| 决策 | 选择 |
|------|------|
| AsyncModule 关系 | Mixin 扩展 Module（方案 2） |
| 默认并发数 | 20~30（均衡） |
| 迁移策略 | 渐进迁移，37 个同步模块通过 to_thread 包装 |

### 三、实施完成 — 2026-05-26 下午

#### 3.1 AsyncModuleMixin（common/async_module.py）— 新建

- aiohttp.ClientSession 并发安全管理（asyncio.Lock + 双重检查）
- async_get / async_post（直连优先，proxy_fallback 可配，指数退避 2^n 上限 30s）
- resp.ok 校验（200-299）
- ssl.SSLError / UnicodeDecodeError 正确分类处理
- async_close 锁保护
- run_async() 默认实现（to_thread → self.run）
- cleanup() 钩子供调度器调用

#### 3.2 Collect 调度器重写（modules/collect.py）

- import threading → import asyncio
- max_concurrent: 50 → 25
- run() 简化为 asyncio.run(self.run_async())
- 新增 run_async(): asyncio.gather + Semaphore(25) 并发执行所有模块
- 新增 _run_module_async(): 异步原生模块直接 await，同步模块通过 daemon Thread + join(timeout) 包装
- 废弃 _run_module() 保留兼容
- module_timeout_override 按 source 自定义超时

#### 3.3 Playwright 模块适配

- modules/search/google.py: 继承 AsyncModuleMixin，新增 run_async()
- modules/search/yahoo.py: 同上
- _search_all() finally 用 asyncio.shield() 防止 CancelledError 导致帧分离

#### 3.4 问题修复

| 问题 | 根因 | 修复 |
|------|------|------|
| Executor 300s 线程残留警告 | ThreadPoolExecutor 持久化，超时线程死等 | 改用 daemon Thread + join(timeout)，超时即放弃 |
| Playwright 帧分离 | CancelledError 中断 browser.close() | finally 加 asyncio.shield |
| VT 超时后仍打印日志 | daemon 线程继续执行 finish() | 线程 join 超时后检查 done Event，精确判定 |

#### 3.5 测试结果

pytest: 270 passed, 7 skipped — 零回归

### 四、泛解析过滤 — 同日完成

#### 4.1 问题

qq.com 通过 VT 收集到 2000+ 子域名，但 check --dns 验证仅几十个存活，
大量为泛解析噪音。

#### 4.2 实现（modules/collect.py）

- collect_config 新增 wildcard_filter: True
- _detect_wildcard_ip(): UUID 随机子域名 DNS 检测
- _filter_wildcard_subdomains(): 并发解析所有收集子域名，移除匹配泛解析 IP 的
- run_async() 流程优化：先检测泛解析 → 若存在则限流 VT max_pages (50→5) → 后置过滤

#### 4.3 其他改进

- VT page_delay / max_pages 改为 settings 可配（VIRUSTOTAL_PAGE_DELAY / VIRUSTOTAL_MAX_PAGES）
- check -i 输出命名改为 check_{域名}.csv

### 五、改动的文件

| 文件 | 改动 |
|------|------|
| common/async_module.py | 新建 |
| modules/collect.py | 重写调度 + 泛解析过滤 |
| modules/search/google.py | AsyncModuleMixin + run_async + shield |
| modules/search/yahoo.py | 同上 |
| config/settings.py | VT 配置字段 |
| config/.env.example | VT 配置文档 |
| justone.py | check -i 输出命名 |

---

*日期: 2026-05-26*
*状态: 完成*
