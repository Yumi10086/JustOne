# Async Collect Architecture Design

> 异步收集架构 — Collect 调度器 asyncio 改造 + AsyncModuleMixin 新增
>
> 日期: 2026-05-26 | 状态: 设计完成 | 来源: JustOne构想.md §9 + brainstorming

---

## 1. 问题

当前 `modules/collect.py` 的 `Collect` 调度器使用 `threading.Thread` 串行执行 39 个模块：

- 一次一个模块 — `max_concurrent=50` 是死代码
- 超时泄漏 — `thread.join(timeout)` 返回后线程变为 daemon 孤儿
- 78 分钟最坏情况
- 已有异步代码孤立 — `AsyncHTTPCheck` 已定义但未接入

## 2. 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| AsyncModule 关系 | `AsyncModuleMixin` 混入 | 复用 Module 状态，不强加给 Playwright |
| 默认并发 | 25 (`asyncio.Semaphore`) | 均衡：避免 API 封 + 内存可控 |
| 37 个同步模块 | `asyncio.to_thread()` | 不改模块代码，零回归 |
| 2 个 Playwright | 暴露 `async run_async()` | 调度器直接 await |

## 3. 架构

```
                         justone.py
                              │
                    ┌─────────▼─────────┐
                    │    Collect.run()   │  async def run()
                    │  asyncio.Semaphore │  默认 25
                    │  asyncio.TaskGroup │  5 类并发
                    └──┬──────┬──────┬───┘
                       │      │      │
              ┌────────▼─┐ ┌──▼──┐ ┌─▼─────────┐
              │ 同步模块  │ │模块 │ │ Playwright │
              │to_thread │ │    │ │ 原生协程   │
              │ (37个)   │ │    │ │  (2个)     │
              └──────────┘ └────┘ └───────────┘
```

## 4. 组件

### 4.1 `common/async_module.py` (新增 ~130 行)

`AsyncModuleMixin` — 提供 `async_get` / `async_post` / `async_close`，基于 aiohttp。

- 并发安全: `asyncio.Lock` + 双重检查，锁内不 await
- 代理策略: `proxy_fallback=False` 直连, `True` 直连→代理兜底
- 指数退避: `min(2^n, 30)` 秒
- `resp.ok` (200-299) 校验
- `ssl.SSLError` / `UnicodeDecodeError` 分类处理，不重试
- `async_close()` 锁保护，关闭后清空引用

### 4.2 `modules/collect.py` (重写 ~100 行)

- `run()` → `async def run()`，`asyncio.TaskGroup` 并发 5 类
- `_run_module()` → `async def _run_module()`，`wait_for()` + `task.cancel()`
- `asyncio.Semaphore(25)` 控制总并发
- `asyncio.to_thread()` 包装同步模块

### 4.3 `modules/search/google.py` & `yahoo.py` (各 +8 行)

新增 `async run_async()`。保留 `run()` 向后兼容。

### 4.4 `justone.py` (1 行)

`asyncio.run(collector.run())`

### 4.5 `modules/check/http.py` (轻改)

`AsyncHTTPCheck` 接入 check 命令。

## 5. 文件清单

| 文件 | 类型 | 行数 |
|------|------|------|
| `common/async_module.py` | 新增 | ~130 |
| `modules/collect.py` | 重写 | ~100 改动 |
| `modules/search/google.py` | 新增 run_async | +8 |
| `modules/search/yahoo.py` | 新增 run_async | +8 |
| `justone.py` | asyncio.run 包装 | ±1 |
| `tests/test_collect.py` | 适配 async | ~10 |
| `modules/check/http.py` | 接入 AsyncHTTPCheck | 轻改 |

## 6. 测试

- `test_collect.py` 改为 `pytest-asyncio`
- 新增 `AsyncModuleMixin` 并发安全测试
- 零回归: 270 passed

## 7. 风险

| 风险 | 缓解 |
|------|------|
| to_thread 线程池耗尽 | 25 Semaphore < 默认 24 线程 |
| Playwright 异常未清理 | CancelledError → finally: browser.close() |
| 模块线程安全 | 36 个同步模块各在独立线程中 |
