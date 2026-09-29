# JustOne 项目开发日志

## 2026-05-11 下午

### 项目概述

**项目目标**：适配 Python 3.14 的子域名收集工具，参考 OneForAll

**技术栈**：
- CLI: Typer
- 进度条: tqdm
- 配置: Pydantic + .env
- 日志: loguru
- HTTP: requests + aiohttp (异步)
- DNS: dnspython

---

## 本次工作：代码耦合度修复

### 1. 消除循环依赖 ✅

**问题**：`domain.py → tldextract.py → utils.py → domain.py` 存在循环依赖

**解决方案**：将 `utils.looks_like_ip()` 函数内联到 `tldextract.py`

**修改文件**：
- `common/tldextract.py` - 添加 `_looks_like_ip()` 函数，移除对 `utils` 的导入

---

### 2. 统一配置管理 ✅

**问题**：项目中有 10+ 个全局配置字典分散在不同模块

**解决方案**：在 `config/settings.py` 中添加 `ConfigManager` 类

**修改文件**：
- `config/settings.py` - 添加 `ConfigManager` 类，提供统一的配置访问
- `config/__init__.py` - 导出 `config_manager`

---

### 3. 合并重复的 Database 类 ✅

**问题**：存在两个 `Database` 类（`database.py` 使用 SQLite，`records.py` 使用 SQLAlchemy）

**解决方案**：标记 `records.py` 为未使用（添加弃用说明）

**修改文件**：
- `common/records.py` - 添加模块级弃用说明

---

### 4. 定义模块接口协议 ✅

**问题**：模块间通过 dict 传递参数，无抽象接口

**解决方案**：创建 `common/protocols.py` 定义标准接口

**新增文件**：
- `common/protocols.py` - 定义 `CollectModule`、`CheckModule`、`ExportModule`、`BruteModule` 协议

---

### 5. 修复测试错误 ✅

**修改文件**：
- `tests/test_module.py` - 修正 `test_default_init` 期望值（27 → 5）

---

### 6. 优化进度条 ✅

**优化**：
- 收集模块进度条：使用简单的 `\r` 单行显示
- 爆破模块进度条：tqdm，每 1% 更新一次（原来 5%）
- 清除 pycache 缓存问题

**修改文件**：
- `justone.py` - 移除 rich 依赖，使用简单进度显示
- `modules/brute.py` - 优化进度条更新频率

---

## 测试统计

| 模块 | 测试数 | 状态 |
|------|--------|------|
| common 模块 | 109 | ✅ |
| modules 模块 | 88 | ✅ |
| check 模块 | 41 | ✅ |
| export 模块 | 25 | ✅ |
| justone.py | 25 | ✅ |
| **总计** | **270** | ✅ |

---

## 后续待做

- [ ] 更多搜索引擎 (Google, FOFA, Hunter)
- [ ] 子域置换模块 (altdns)
- [ ] 子域接管检测、端口扫描
- [ ] FOFA/Hunter API 集成
- [ ] 收集模块异步化
- [ ] Pydantic 配置类迁移到 V2 写法

---

*最后更新: 2026-05-11*
*累计完成: 270 个测试*
*状态: 代码耦合度修复完成，耦合度评分: 6→7*