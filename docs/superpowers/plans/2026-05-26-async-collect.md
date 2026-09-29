# 异步收集调度器实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Collect 调度器从串行 threading 改造为 asyncio 驱动的并发调度器，39 个模块并行执行，预期总耗时从 ~N×30s 降至 max(module)×30s。

**Architecture:** 采用 Mixin 模式（方案 2）——新增 `AsyncModuleMixin` 为已有 Module 子类提供 aiohttp 异步 HTTP 能力，不破坏现有 Module 接口。调度器通过 `asyncio.gather` 并发执行模块，同步模块经 `asyncio.to_thread` 包装，Playwright 模块暴露 `run_async()` 直接参与事件循环。

**Tech Stack:** Python 3.14, asyncio, aiohttp, Playwright (现有), threading (to_thread 回退)

---

## 文件结构

| 文件 | 角色 | 操作 |
|------|------|------|
| `common/async_module.py` | AsyncModuleMixin — aiohttp session 管理 + 异步 HTTP 方法 | **新建** |
| `modules/collect.py` | Collect 调度器 — run() 改写为 async，并行调度所有模块 | **重写核心方法** |
| `modules/search/google.py` | Google 搜索 — 暴露 run_async()，移除嵌套 asyncio.run | **重构 run()** |
| `modules/search/yahoo.py` | Yahoo 搜索 — 同 Google | **重构 run()** |
| `justone.py` | CLI 入口 — Collect 调用改为 asyncio.run(c.run_async()) | **修改 1 行** |
| `modules/check/http.py` | AsyncHTTPCheck — 接入新调度器（按需，非核心） | **可选** |

---

### Task 1: 创建 AsyncModuleMixin（common/async_module.py）

**Files:**
- Create: `common/async_module.py`
- Modify: 无

- [ ] **Step 1: 创建 AsyncModuleMixin 类**

```python
# common/async_module.py
"""
异步 HTTP 请求 Mixin

为 Module 子类提供基于 aiohttp 的异步 HTTP 能力，
与 requests 基类共存，不破坏现有接口。
"""

import asyncio
import random
from typing import Optional, Dict, Any

import aiohttp

from config.logging import logger


class AsyncModuleMixin:
    """
    异步 HTTP 请求 Mixin

    使用方式（MRO 要求 Module 在前）:
        class MyMod(Module, AsyncModuleMixin):
            ...
    """

    def __init__(self, *args, **kwargs):
        """Mixin 初始化，必须配合 super().__init__"""
        super().__init__(*args, **kwargs)
        self._async_session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    async def _get_async_session(self) -> aiohttp.ClientSession:
        """
        获取或创建 aiohttp ClientSession（并发安全，双重检查锁）

        :return: aiohttp.ClientSession 实例
        """
        if self._async_session is None:
            async with self._session_lock:
                if self._async_session is None:
                    timeout = aiohttp.ClientTimeout(total=self.timeout)
                    connector = aiohttp.TCPConnector(verify_ssl=self.verify)
                    self._async_session = aiohttp.ClientSession(
                        timeout=timeout,
                        connector=connector,
                    )
        return self._async_session

    async def async_get(
        self, url: str, params: dict = None, check: bool = True,
        ignore: bool = False, **kwargs
    ) -> Optional[str]:
        """
        异步 GET 请求，直连优先，代理回退 + 指数退避

        :param str url: 请求 URL
        :param dict params: 查询参数
        :param bool check: 是否校验 HTTP 状态码
        :param bool ignore: 是否降级日志
        :param kwargs: 传递给 aiohttp 的额外参数
        :return: 响应文本，失败返回 None
        """
        level = 'DEBUG' if ignore else 'ERROR'
        session = await self._get_async_session()
        headers = self.header.copy() if self.header else {}
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))

        for attempt in range(self.request_retries):
            proxy = self.proxy if attempt == 1 else None
            backoff = min(2 ** attempt, 30)

            try:
                async with session.get(
                    url, params=params, headers=headers,
                    proxy=proxy, **kwargs
                ) as resp:
                    if check and resp.status not in range(200, 300):
                        logger.debug(
                            f'async_get {url[:80]} 返回状态码 {resp.status}，跳过'
                        )
                        return None
                    return await resp.text()
            except aiohttp.ClientSSLError as e:
                logger.log(level, f'SSL 错误: {str(e)[:100]}')
                return None
            except UnicodeDecodeError as e:
                logger.log(level, f'编码错误: {str(e)[:100]}')
                return None
            except (aiohttp.ClientConnectorError,
                    aiohttp.ClientProxyConnectionError,
                    aiohttp.ServerTimeoutError,
                    asyncio.TimeoutError) as e:
                if attempt == 0 and self.proxy:
                    logger.debug(
                        f'直连失败，{backoff}s 后尝试代理: {str(e)[:80]}'
                    )
                    await asyncio.sleep(backoff + random.uniform(0, 1))
                    continue
                logger.log(level, f'async_get 失败: {str(e)[:100]}')
                return None
            except Exception as e:
                if attempt == 0 and self.proxy:
                    logger.debug(
                        f'直连失败，{backoff}s 后尝试代理: {str(e)[:80]}'
                    )
                    await asyncio.sleep(backoff + random.uniform(0, 1))
                    continue
                logger.log(level, f'async_get 失败: {str(e)[:100]}')
                return None

        return None

    async def async_post(
        self, url: str, data: dict = None, check: bool = True,
        **kwargs
    ) -> Optional[str]:
        """
        异步 POST 请求，直连优先，代理回退

        :param str url: 请求 URL
        :param dict data: 请求体
        :param bool check: 是否校验 HTTP 状态码
        :param kwargs: 传递给 aiohttp 的额外参数
        :return: 响应文本，失败返回 None
        """
        session = await self._get_async_session()
        headers = self.header.copy() if self.header else {}
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))

        for attempt in range(self.request_retries):
            proxy = self.proxy if attempt == 1 else None
            backoff = min(2 ** attempt, 30)

            try:
                async with session.post(
                    url, data=data, headers=headers,
                    proxy=proxy, **kwargs
                ) as resp:
                    if check and resp.status not in range(200, 300):
                        logger.debug(
                            f'async_post {url[:80]} 返回状态码 {resp.status}'
                        )
                        return None
                    return await resp.text()
            except aiohttp.ClientSSLError as e:
                logger.error(f'SSL 错误: {str(e)[:100]}')
                return None
            except UnicodeDecodeError as e:
                logger.error(f'编码错误: {str(e)[:100]}')
                return None
            except (aiohttp.ClientConnectorError,
                    aiohttp.ServerTimeoutError,
                    asyncio.TimeoutError) as e:
                if attempt == 0 and self.proxy:
                    logger.debug(
                        f'直连失败，{backoff}s 后尝试代理: {str(e)[:80]}'
                    )
                    await asyncio.sleep(backoff + random.uniform(0, 1))
                    continue
                logger.error(f'async_post 失败: {str(e)[:100]}')
                return None
            except Exception as e:
                if attempt == 0 and self.proxy:
                    logger.debug(
                        f'直连失败，{backoff}s 后尝试代理: {str(e)[:80]}'
                    )
                    await asyncio.sleep(backoff + random.uniform(0, 1))
                    continue
                logger.error(f'async_post 失败: {str(e)[:100]}')
                return None

        return None

    async def async_close(self):
        """关闭 aiohttp ClientSession（并发安全）"""
        async with self._session_lock:
            if self._async_session:
                await self._async_session.close()
                self._async_session = None

    # ----- 调度器协作接口 -----

    async def run_async(self) -> set:
        """
        异步执行入口（默认实现：to_thread 调用同步 run()）

        异步原生模块（Google/Yahoo 等）应覆盖此方法。
        :return: 子域名集合
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run)

    async def cleanup(self):
        """模块清理钩子（调度器在完成后调用）"""
        await self.async_close()
```

- [ ] **Step 2: 验证语法 — Python import 测试**

```bash
python -c "from common.async_module import AsyncModuleMixin; print('OK')"
```
Expected: `OK`，无异常。

---

### Task 2: 重写 Collect 调度器（modules/collect.py）

**Files:**
- Modify: `modules/collect.py`（重写 `run()` 和 `_run_module()`，新增 `run_async()`）

- [ ] **Step 1: 添加 import**

在 `modules/collect.py` 顶部添加 asyncio 导入（替换 threading）：

```python
# modules/collect.py — 顶部 import 区域修改
import time
import asyncio
from typing import Optional, Set, List, Dict, Any, Type
from concurrent.futures import TimeoutError as FutureTimeoutError

from config.logging import logger
from common.domain import Domain
```

删除原有 `import threading`（若存在）。

- [ ] **Step 2: 修改默认并发配置**

```python
# collect_config 中修改 max_concurrent
collect_config = {
    'enabled': True,
    'module_timeout': 120,
    'max_concurrent': 25,       # 从 50 改为 25（实际生效值）
    'save_module_result': False,
    'enable_search': True,
    'enable_certificate': True,
    'enable_dataset': True,
    'enable_intelligence': True,
}
```

- [ ] **Step 3: 改写 run() 为 sync wrapper**

```python
def run(self) -> List[str]:
    """
    执行收集任务（同步入口，内部调用 asyncio.run）

    :return: 子域名列表
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(self.run_async())
    else:
        # 已有运行中的事件循环 → 创建新线程运行
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, self.run_async())
            return future.result()
```

- [ ] **Step 4: 新增 run_async() 主方法**

```python
async def run_async(self) -> List[str]:
    """
    异步执行收集任务（asyncio 原生入口）

    并发调度所有模块类型，每个模块独立超时保护。
    :return: 子域名列表
    """
    logger.info(f'开始收集 {self.domain} 的子域名')
    self.start_time = time.time()

    all_modules = (
        self.search_modules + self.certificate_modules +
        self.dataset_modules + self.dnsquery_modules +
        self.intelligence_modules
    )

    total = len(all_modules)
    logger.info(f'并发执行 {total} 个模块（并发数: {self.max_concurrent}）')

    semaphore = asyncio.Semaphore(self.max_concurrent)

    async def _run_with_semaphore(module):
        async with semaphore:
            return await self._run_module_async(module)

    tasks = [_run_with_semaphore(m) for m in all_modules if m is not None]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for module, result in zip(all_modules, results):
        if isinstance(result, Exception):
            module_name = getattr(module, 'module', 'unknown')
            logger.error(f'{module_name} 模块异常: {result}')
            continue
        if result is None:
            continue
        module_name = getattr(module, 'module', 'unknown')
        self.add_subdomains(result[0], module_name)

    # 清理所有模块的异步资源
    for module in all_modules:
        if hasattr(module, 'cleanup'):
            try:
                await asyncio.wait_for(module.cleanup(), timeout=5)
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

    self.end_time = time.time()
    self.elapse = round(self.end_time - self.start_time, 1)
    logger.info(
        f'收集完成，共发现 {len(self.subdomains)} 个子域名，'
        f'耗时 {self.elapse} 秒'
    )

    return list(self.subdomains)
```

- [ ] **Step 5: 新增 _run_module_async() 替代 _run_module()**

```python
async def _run_module_async(self, module: Any) -> Optional[tuple]:
    """
    异步执行单个模块（带超时保护）

    :param module: 模块实例
    :return: (子域名集合, 耗时) 或 None
    """
    source = getattr(module, 'source', 'unknown')
    module_name = getattr(module, 'module', 'Unknown')

    try:
        logger.info(f'执行 {source} 模块')
        module_start = time.time()

        if asyncio.iscoroutinefunction(
            getattr(module, 'run_async', None)
        ):
            # 异步原生模块（Google/Yahoo/异步自定义模块）
            result = await asyncio.wait_for(
                module.run_async(), timeout=self.module_timeout
            )
        else:
            # 同步模块 → to_thread 包装
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, module.run),
                timeout=self.module_timeout,
            )

        module_elapse = round(time.time() - module_start, 1)
        logger.info(
            f'{source} 模块完成，发现 {len(result)} 个子域名，'
            f'耗时 {module_elapse} 秒'
        )
        return (result, module_elapse)

    except asyncio.TimeoutError:
        logger.error(
            f'{source} 模块执行超时（{self.module_timeout}秒），跳过'
        )
        return None
    except Exception as e:
        logger.error(f'{source} 模块执行出错: {e}')
        return None
```

- [ ] **Step 6: 标记旧 _run_module 为废弃（保留兼容）**

旧 `_run_module()` 方法保留不动，添加注释 `# 废弃：保留用于兼容，新代码请使用 _run_module_async`。

- [ ] **Step 7: 删除 _run_*_modules 中的 for 循环调用**

原有的 `_run_search_modules`, `_run_certificate_modules` 等方法中逐个调用 `_run_module` 的 for 循环不再被 `run_async()` 使用。**保留这些方法本身**，因为 `run()` sync wrapper 在单线程场景下可能仍需要它们。

不，更简洁的做法：`run()` 现在只调用 `run_async()`，不再需要这些串行方法。但保留它们作为公共 API（外部可能调用）。

让我简化：**不移除任何方法**，只在 `run()` 中改为调用 `run_async()`，并新增 `run_async()` 作为主入口。

- [ ] **Step 8: 验证语法**

```bash
python -c "from modules.collect import Collect; print('OK')"
```
Expected: `OK`

---

### Task 3: 重构 Google 搜索模块（modules/search/google.py）

**Files:**
- Modify: `modules/search/google.py`

- [ ] **Step 1: 修改类定义添加 AsyncModuleMixin**

```python
# 修改 import（添加 AsyncModuleMixin）
from common.async_module import AsyncModuleMixin

# 修改类定义
class Google(Search, AsyncModuleMixin):
```

注意 MRO 顺序：Search(Module) 在前，AsyncModuleMixin 在后。`super().__init__` 将按 MRO 正确初始化 Module 和 AsyncModuleMixin。

- [ ] **Step 2: 新增 run_async() 方法**

```python
async def run_async(self) -> Set[str]:
    """异步执行 Google Web 搜索（供调度器直接调用）"""
    self.begin()
    await self._search_all()
    self.finish()
    self.save_json()
    self.gen_result()
    self.save_db()
    return self.subdomains
```

- [ ] **Step 3: 修改 run() 为兼容包装**

```python
def run(self) -> Set[str]:
    """执行 Google Web 搜索（同步入口，兼容旧调用）"""
    self.begin()
    asyncio.run(self._search_all())
    self.finish()
    self.save_json()
    self.gen_result()
    self.save_db()
    return self.subdomains
```

保持 `run()` 不变也可以，但由于现在 Google 继承了 AsyncModuleMixin，`run()` 中的 `asyncio.run()` 在调度器调用 `run_async()` 时不会被触发。`run_async()` 是调度器的新入口，直接执行异步代码，无需 `asyncio.run` 桥接。

- [ ] **Step 4: 模块级 run 函数保持不变**

```python
def run(domain: str, config: Optional[dict] = None) -> Set[str]:
    module = Google(domain, config)
    return module.run()
```
模块级 `run()` 调用实例的 `run()` → 触发兼容同步路径，行为不变。

---

### Task 4: 重构 Yahoo 搜索模块（modules/search/yahoo.py）

**Files:**
- Modify: `modules/search/yahoo.py`

与 Google 完全相同的改造模式。

- [ ] **Step 1: 修改类定义**

```python
# 修改 import
from common.async_module import AsyncModuleMixin

# 修改类定义
class Yahoo(Search, AsyncModuleMixin):
```

- [ ] **Step 2: 新增 run_async() 方法**

```python
async def run_async(self) -> Set[str]:
    """异步执行 Yahoo 搜索（供调度器直接调用）"""
    self.begin()
    await self._search_all()
    self.finish()
    self.save_json()
    self.gen_result()
    self.save_db()
    return self.subdomains
```

- [ ] **Step 3: run() 保持现有实现不变**

`run()` 保持 `asyncio.run(self._search_all())` 不变。调度器调用 `run_async()`，旧代码调用 `run()`，两条路径互不干扰。

---

### Task 5: 更新 CLI 入口（justone.py）

**Files:**
- Modify: `justone.py`

- [ ] **Step 1: 修改 Collect 调用**

在 `justone.py` 的 `main()` 命令中，找到以下代码：

```python
collect = Collect(main_domain, config)
subdomains = set(collect.run())
```

改为：

```python
collect = Collect(main_domain, config)
subdomains = set(collect.run())  # run() 内部已处理 asyncio
```

实际上 `collect.run()` 现在内部已处理事件循环创建（见 Task 2 Step 3），所以 CLI 调用无需修改。`run()` 的 sync wrapper 会创建新事件循环或复用现有事件循环。

**结论：justone.py 无需修改。** `Collect.run()` 保持同步签名，内部透明切换为 asyncio。

- [ ] **Step 2: 验证 CLI 不变**

```bash
python justone.py main --help
```
Expected: 帮助输出正常，无 import 错误。

---

### Task 6: 可选 — AsyncHTTPCheck 接入（modules/check/http.py）

**Files:**
- Modify: `modules/check/http.py`

此为可选任务，AsyncHTTPCheck 本身已是完全的 asyncio 实现，run() 通过 `asyncio.run()` 桥接。如果后续 `check` 命令也需要并发优化，可以为其添加 `run_async()` 方法。

当前 `check` 命令不在 Collect 调度器内（独立命令），因此**暂不修改**。

---

### Task 7: 测试与验证

**Files:**
- 无修改

- [ ] **Step 1: 运行完整测试套件**

```bash
pytest tests/ -v --tb=short 2>&1
```
Expected: 270 passed, 7 skipped（与改造前一致）

- [ ] **Step 2: 运行 Collect 相关测试**

```bash
pytest tests/ -k "collect" -v --tb=short 2>&1
```
Expected: 所有 Collect 相关测试通过。

- [ ] **Step 3: 运行搜索模块测试**

```bash
pytest tests/test_search_google.py tests/test_search_yahoo.py -v --tb=short 2>&1
```
Expected: 通过（或跳过，若无 API key/Playwright）

- [ ] **Step 4: 验证 dry-run（无 API key 的空跑）**

```bash
python justone.py main example.com --no-brute --no-search --no-cert --no-dataset -v 2>&1
```
Expected: 正常执行（0 个模块或少量模块），无崩溃。

---

## Self-Review

**1. Spec coverage:**
- ✅ AsyncModuleMixin 创建（Task 1）
- ✅ Collect 调度器并发化（Task 2）
- ✅ Google run_async 暴露（Task 3）
- ✅ Yahoo run_async 暴露（Task 4）
- ✅ CLI 入口适配（Task 5 — 确认无需改）
- ✅ AsyncHTTPCheck 评估（Task 6 — 暂不改）
- ✅ 测试验证（Task 7）

**2. Placeholder scan:** 无 TBD/TODO/占位符。

**3. Type consistency:**
- `run_async()` → `Set[str]`（Google/Yahoo/Mixin）
- `_run_module_async()` → `Optional[tuple]`
- `Collect.run_async()` → `List[str]`
- `Collect.run()` → `List[str]`（保持不变）

所有签名一致，无冲突。

---

## 验证清单

- [ ] `python -c "from common.async_module import AsyncModuleMixin"` 正常
- [ ] `python -c "from modules.collect import Collect"` 正常
- [ ] `python -c "from modules.search.google import Google"` 正常
- [ ] `python -c "from modules.search.yahoo import Yahoo"` 正常
- [ ] `pytest` 结果：270 passed, 7 skipped
- [ ] `python justone.py main --help` 正常
- [ ] `python justone.py main example.com --no-brute --no-search --no-cert --no-dataset -v` 不崩溃
