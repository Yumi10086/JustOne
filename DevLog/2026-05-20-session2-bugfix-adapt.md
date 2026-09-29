# JustOne 项目开发日志

## 2026-05-20 (第二轮)

### 一、so.py / sogou.py 搜索引擎适配

从 OneForAll 适配 360 搜索和搜狗搜索模块。

| 文件 | 类 | 引擎 | 适配要点 |
|------|-----|------|---------|
| `so.py` | SoSearch | 360搜索 | `Search.__init__` → `super().__init__`，添加类型标注/中文 docstring |
| `sogou.py` | SogouSearch | 搜狗搜索 | 同上，搜索参数 `query`/`page`/`num` |

集成：`__init__.py` 和 `collect.py` 注册，搜索引擎共 12 个。

---

### 二、check --dns 功能修复

`justone.py:263` 处 `show_progress=True` 在 `--dns` 模式下传给了不接收该参数的 `DNSCheck.run()`。

修复：分支调用，`--dns` 时调 `DNSCheck.run(subdomains)`，默认调 `AsyncHTTPCheck.run(subdomains, show_progress=True)`。

---

### 三、HTTP 请求代理降级机制

`common/module.py` 新增 `_do_get` / `_do_post` 请求重试逻辑：

**策略：直连优先 → 代理兜底**（`request_retries=2`）

| 尝试 | 连接方式 | 失败时 |
|------|---------|--------|
| 1 | 直连 `proxies=None` | 有代理则重试 |
| 2 | 代理 `proxies=self.proxy` | 抛出异常 |

- 捕获 `ProxyError` / `SSLError` / `ConnectionError` 触发降级
- `get()` 和 `post()` 均走统一重试逻辑
- 未配置代理时只尝试 1 次直连

---

### 四、删除 cebaidu 模块

`ce.baidu.com` 已停止服务，删除 `modules/datasets/cebaidu.py`。

删除检查清单：
1. ? 删除源文件
2. ? `datasets/__init__.py` 移除导入和导出
3. ? `collect.py` 移除导入和实例化
4. ? 无 API key 字段，不需要改 settings/.env

---

### 测试结果

**270 passed, 7 skipped, 0 failed**

---

*日期: 2026-05-20*
*状态: 模块适配 + Bug 修复 + 代理优化 + 模块清理完成，零回归*
