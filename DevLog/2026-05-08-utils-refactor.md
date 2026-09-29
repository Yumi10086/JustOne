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
├── common/             # 公共模块 (适配中)
├── modules/            # 功能模块 (待实现)
├── data/               # 数据资源
└── results/            # 结果输出
```

---

## 工作进度

### 2026-05-08 (对话中完成)

#### 1. 配置系统重构 ✅ (5月8日)

| 文件 | 状态 | 说明 |
|------|------|------|
| config/settings.py | ✅ | 基于 pydantic_settings.BaseSettings 支持 .env |
| config/logging.py | ✅ | 控制台/文件日志格式化 |
| common/domain.py | ⚠️ | 需修复配置依赖 |
| common/utils.py | 🔄 | 已重构 (见下方) |
| common/module.py | ⚠️ | 需修复配置依赖 |
| common/database.py | ⚠️ | 需改用 sqlite3 |
| common/records.py | ✅ | 保留 |
| common/tldextract.py | ✅ | 循环依赖已解决 |
| common/ipreg.py | ⚠️ | 需修复配置依赖 |
| common/ipasn.py | ⚠️ | 需修复配置依赖 |
| common/resolve.py | ⚠️ | 需修复配置依赖 |
| common/similarity.py | ✅ | 无需修改 |

#### 2. utils.py 重构 ✅ (本次对话)

**文件**：`common/utils.py`

**变更内容**：

| 变更 | 说明 |
|------|------|
| ❌ 移除 tenacity | 改用 `asyncio` 内置重试 |
| ❌ 移除 SQLAlchemy | 移除 records 库依赖 |
| ❌ 移除 settings 强依赖 | 改用 `http_config` 字典 + `set_http_config()` |
| ✅ 保留核心函数 | `match_subdomains`, `dns_query`, `get_url_resp` |
| ✅ 新配置方式 | 全局 `http_config` 字典可配置 |

**移除的函数** (将在后续重写)：
- `save_to_db`, `count_alive`, `init_table` → 改用 sqlite3
- `export_all_results`, `export_all` → 简化导出
- `call_massdns`, `get_massdns_path` → 外部工具依赖
- `check_dep` → 不需要 (仅支持 3.14+)

**保留的函数**：
- `match_subdomains()` - 子域名正则匹配
- `looks_like_ip()` - IP 地址检测
- `dns_resolver()` / `dns_query()` - DNS 查询
- `get_url_resp()` - HTTP 请求
- `check_net_async()` - 异步网络检测
- `http_config` + `set_http_config()` - 配置管理

**配置字段映射变更**：
- `settings.http_timeout` → `http_config['timeout']`
- `settings.http_verify_ssl` → `http_config['verify_ssl']`
- `settings.proxy_enable` → `http_config['proxy_enable']`
- `settings.dns_nameservers` → `http_config['dns_nameservers']`

---

#### 3. Skill 创建 ✅ (本次对话)

| Skill | 路径 | 说明 |
|-------|------|------|
| review-conversation | C:/Users/KK/.agents/skills/review-conversation/ | 回顾对话 |
| summarize-log | C:/Users/KK/.agents/skills/summarize-log/ | 生成工作日志 |

---

## 后续工作 (待完成)

### Phase 1: 基础设施
- [x] 安装依赖：`pip install pydantic-settings`
- [ ] 适配 modules 目录下的模块
- [ ] 重构 database.py 改用 sqlite3 (pending: utils.py 完成)

### Phase 2: 核心功能 (待实现)
- [ ] 修复 common/*.py 配置依赖
  - [ ] domain.py
  - [ ] module.py
  - [ ] ipreg.py
  - [ ] ipasn.py
  - [ ] resolve.py
- [ ] CLI 入口 (justone.py)
- [ ] 收集调度器 (modules/collect.py)

### Phase 3: 收集模块 (待实现)
- [ ] 搜索引擎模块 (baidu, bing, google, fofa)
- [ ] 证书查询模块 (crtsh)
- [ ] 数据集查询模块
- [ ] DNS 查询模块

### Phase 4: 扩展功能 (待实现)
- [ ] 子域爆破模块
- [ ] 子域置换模块
- [ ] 子域接管检测
- [ ] 结果导出

---

## 依赖对比

### 原有依赖 vs 目标依赖

| 原有 | 目标 | 状态 |
|------|------|------|
| tenacity | asyncio (内置) | ✅ 已替换 |
| SQLAlchemy | sqlite3 (内置) | ⏳ pending |
| records (tablib) | 简化导出 | ⏳ pending |
| dnspython | dnspython | ✅ 保留 |
| requests | requests | ✅ 保留 |
| pydantic | pydantic | ✅ 保留 |

---

## 关键设计要点

### 子域结果结构
```python
{
    'subdomain': str,   # 子域名
    'domain': str,      # 主域名
    'resolve': int,     # 是否解析成功 (0/1)
    'alive': int,       # 是否存活 (0/1)
    'ip': str,         # IP地址
    'cname': str,      # CNAME
    'port': int,       # 端口
    'level': int,      # 子域层级
    'cdn': int,        # 是否CDN
    'module': str,     # 发现模块
    'source': str,     # 数据源
}
```

### 配置优先级
1. 命令行参数 (最高)
2. 环境变量 (.env)
3. 配置文件 (settings.py)
4. 默认值 (最低)

---

*最后更新: 2026-05-08*