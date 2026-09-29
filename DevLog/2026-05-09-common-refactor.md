# JustOne 项目开发日志

## 项目概述

**目标**：适配 Python 3.14 的子域名收集工具，参考 OneForAll

**技术栈**：
- CLI: Typer
- 进度条: tqdm
- 配置: Pydantic + .env
- 日志: loguru
- HTTP: requests + aiohttp (异步)
- DNS: dnspython

**目录结构**：
```
JustOne/
├── justone.py          # Typer CLI 入口
├── config/             # 配置模块 ✅ 已完成
├── common/             # 公共模块 ✅ 已完成适配
├── modules/            # 功能模块 (待实现)
├── data/               # 数据资源
├── results/            # 结果输出
└── tests/              # 单元测试 ✅
```

---

## 工作进度

### 2026-05-09 (本次对话完成)

#### 1. database.py 适配与修复 ✅

**问题修复**：
- 移除 `from config import settings` 依赖
- 默认路径改为 `db_config['results_dir']`
- 添加 `set_db_config()` 全局配置函数
- 修复 Python 3.14 兼容性（cursor 不支持 context manager）
- QueryResult 迭代器修复
- 添加 PRAGMA 优化（WAL 模式）

**创建测试**：`tests/test_database.py` (22 个测试)

---

#### 2. module.py 适配 ✅

**变更内容**：
- 移除 `settings` 依赖
- 改用 `http_config` 字典 + 实例级 `config`
- 添加 `set_http_config()` 函数
- 移除 threading.Lock（后续可改用 asyncio）
- `save_db()` 接受 `db_path` 参数

**创建测试**：`tests/test_module.py` (32 个测试)

---

#### 3. domain.py 适配 ✅

**变更内容**：
- 移除 `settings` 依赖
- 改用 `data_config` + `set_data_config()`
- 延迟导入 `TLDExtract` 避免循环依赖

**创建测试**：`tests/test_domain.py` (22 个测试)

---

#### 4. resolve.py 重构 ✅

**变更内容**：
- 移除 massdns 外部工具依赖
- 改用 dnspython 实现 DNS 解析
- 添加 `resolve_domain()` 单域解析
- 添加 `resolve_batch()` 批量解析
- 移除 `settings` 依赖

**创建测试**：`tests/test_resolve.py` (18 个测试)

---

#### 5. ipreg.py 适配 ✅

**变更内容**：
- 移除 `settings` 依赖
- 改用 `ipreg_config` + `set_ipreg_config()`

**创建测试**：`tests/test_ipreg.py` (8 个测试)

---

#### 6. ipasn.py 适配 ✅

**变更内容**：
- 移除 `settings` 依赖
- 改用 `ip_asn_config` + `set_ip_asn_config()`
- 修复继承 Database 的兼容性问题

**创建测试**：`tests/test_ipasn.py` (7 个测试)

---

#### 7. 编码风格统一 ✅

**统一内容**：
- 模块 docstring 改为中文
- 函数/方法 docstring 改为中文
- 类 docstring 改为中文
- 日志输出改为中文
- 导入顺序：标准库 → 第三方 → 本项目

**已统一文件**：
| 文件 | 测试数 |
|------|--------|
| module.py | 32 |
| database.py | 22 |
| domain.py | 22 |
| resolve.py | 18 |
| ipreg.py | 8 |
| ipasn.py | 7 |
| utils.py | 109 |
| async_request.py | 109 |
| similarity.py | 109 |
| tldextract.py | 109 |

---

#### 8. 单元测试完善 ✅

**测试覆盖**：
- 所有 common 模块都有对应测试
- 测试使用 unittest 框架
- 添加 sys.path 处理解决导入问题

**测试结果**：
```
Ran 109 tests in 0.4xx s
OK
```

---

#### 9. Skill 创建 ✅

| Skill | 位置 | 说明 |
|-------|------|------|
| auto-test-generator | JustOne/.skills/ | 自动生成测试文件 |
| code-style-unifier | JustOne/.skills/ | 统一代码风格 |

---

## 依赖状态总结

| 依赖 | 原状态 | 新状态 |
|------|--------|--------|
| tenacity | 需安装 | ❌ 已移除 (用 asyncio) |
| SQLAlchemy | 需安装 | ❌ 已移除 (用 sqlite3) |
| records | 需安装 | ❌ 已移除 (用 sqlite3) |
| dnspython | 需安装 | ✅ 保留 |
| requests | 需安装 | ✅ 保留 |
| pydantic | 需安装 | ✅ 保留 |
| aiohttp | 需安装 | ✅ 保留 |

---

## 配置模式说明

每个模块采用统一的配置模式：

```python
# 全局配置
config = {
    'key': 'value',
}

def set_config(config: dict):
    """设置全局配置"""
    config.update(config)

# 实例配置
class MyClass:
    def __init__(self, config: dict = None):
        cfg = config or {}
        self.value = cfg.get('key', config.get('key'))
```

已适配模块：
- `http_config` + `set_http_config()` (module.py, utils.py)
- `db_config` + `set_db_config()` (database.py)
- `data_config` + `set_data_config()` (domain.py)
- `resolve_config` + `set_resolve_config()` (resolve.py)
- `ipreg_config` + `set_ipreg_config()` (ipreg.py)
- `ip_asn_config` + `set_ip_asn_config()` (ipasn.py)

---

## 后续工作

### Phase 1: CLI 入口 (待实现)
- [ ] justone.py - Typer CLI 主入口

### Phase 2: 收集调度器 (待实现)
- [ ] modules/collect.py - 收集调度器

### Phase 3: 功能模块 (待实现)
- [ ] 搜索引擎模块 (baidu, bing, google, fofa)
- [ ] 证书查询模块 (crtsh)
- [ ] 数据集查询模块 (leakix)
- [ ] 子域验证模块 (http, dns)

### Phase 4: 扩展功能 (待实现)
- [ ] 子域爆破模块
- [ ] 子域置换模块
- [ ] 结果导出

---

*最后更新: 2026-05-09*
*累计完成: 10 个 common 模块适配 + 109 个测试*