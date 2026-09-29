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
├── common/             # 公共模块 ✅ 已适配
├── modules/            # 功能模块 (待实现)
├── data/               # 数据资源
└── results/            # 结果输出
```

---

## 工作进度

### 2026-05-08 (已完成)

#### 1. 配置系统重构 ✅

**文件**：`config/settings.py`
- 基于 `pydantic_settings.BaseSettings` 支持 .env 文件读取
- 所有配置带中文注释
- HTTP 线程数自动根据 CPU 核心数计算
- DNS 服务器使用固定值（5个常用 DNS）

**文件**：`config/default.py`
- 默认配置备份

**文件**：`config/api.py`
- API 凭证配置（FOFA、Shodan、VirusTotal 等）

**文件**：`config/.env.example`
- 环境变量示例

#### 2. 日志系统改进 ✅

**文件**：`config/logging.py`
- 控制台日志增加模块名和行号
- 文件日志增加函数名
- 添加 UTF-8 编码支持

#### 3. common 模块适配 ✅

| 文件 | 状态 | 说明 |
|------|------|------|
| domain.py | ✅ | 修复 import 路径，配置字段 |
| utils.py | ✅ | 修复所有配置字段引用 |
| module.py | ✅ | 修复配置字段引用 |
| database.py | ✅ | 修复 import 路径 |
| records.py | ✅ | 修复 tablib 导入 |
| tldextract.py | ✅ | 解决循环依赖 |
| ipreg.py | ✅ | 配置字段 |
| ipasn.py | ✅ | 配置字段 |
| resolve.py | ✅ | 配置字段 |
| similarity.py | ✅ | 无需修改 |

**配置字段映射**：
- `data_storage_dir` → `data_dir`
- `result_save_dir` → `results_dir`
- `enable_random_ua` → `http_enable_random_ua`
- `request_timeout_second` → `http_timeout`
- `request_ssl_verify` → `http_verify_ssl`

#### 4. 开发工具 ✅

- **DevLog**：`DevLog/2026-05-08-config-refactor.md`
- **回顾对话 Skill**：`C:/Users/KK/.agents/skills/review-conversation/`

---

## 后续工作 (待完成)

### Phase 1: 基础设施
- [x] 安装依赖：`pip install pydantic-settings`
- [ ] 适配 modules 目录下的模块

### Phase 2: 核心功能 (待实现)
- [ ] CLI 入口 (justone.py)
- [ ] 收集调度器 (modules/collect.py)
- [ ] 子域匹配逻辑
- [ ] 子域验证模块

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

## 关键设计要点

### 子域结果结构
```python
{
    'subdomain': str,   # 子域名
    'domain': str,      # 主域名
    'resolve': int,     # 是否解析成功 (0/1)
    'alive': int,       # 是否存活 (0/1)
    'ip': str,          # IP地址
    'cname': str,       # CNAME
    'port': int,        # 端口
    'level': int,       # 子域层级
    'cdn': int,         # 是否CDN
    'module': str,      # 发现模块
    'source': str,      # 数据源
}
```

### 配置优先级
1. 命令行参数 (最高)
2. 环境变量 (.env)
3. 配置文件 (settings.py)
4. 默认值 (最低)