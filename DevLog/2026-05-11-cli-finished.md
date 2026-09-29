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

---

## 工作进度

### 2026-05-09 (上次对话)

已完成 **10 个 common 模块** 适配和单元测试。

---

### 2026-05-11 上午

完成了 **modules 目录结构**：
- collect.py, brute.py, export.py
- search/, certificates/, datasets/, check/, dnsquery/, intelligence/
- 共 46 个模块测试

---

### 2026-05-11 下午

#### 1. 修复 get_logger 函数 ✅

在 `common/utils.py` 添加 `get_logger()` 函数

#### 2. 完善 collect.py 模块集成 ✅

- `_init_modules()` 自动加载各类型模块
- `_run_module()` - 统一执行单个模块
- `add_module()` - 添加自定义模块
- `get_summary()` - 获取收集摘要

#### 3. 完善子模块逻辑 ✅

**baidu.py, bing.py, crtsh.py, leakix.py**：
- 添加 `run()` 模块入口函数
- 优化日志输出和错误处理

#### 4. justone.py Typer CLI 入口 ✅

**命令**：
```bash
# 主收集命令
python justone.py example.com

# 指定输出
python justone.py example.com -o results.csv

# 禁用爆破
python justone.py example.com --no-brute

# 禁用特定模块
python justone.py example.com --no-search --no-cert

# 仅爆破
python justone.py brute example.com -w wordlist.txt

# 检查存活
python justone.py check example.com --dns
```

---

## 测试统计

| 模块 | 测试数 |
|------|--------|
| common 模块 | 109 |
| modules 模块 | 88 |
| justone.py | 6 |
| **总计** | **203** |

---

## 项目结构

```
JustOne/
├── justone.py              # CLI 入口 (Typer)
├── config/                 # 配置模块
│   ├── settings.py        # Pydantic 配置
│   └── logging.py         # 日志系统
├── common/                 # 公共模块 (10个)
│   ├── module.py          # 模块基类
│   ├── domain.py          # 域名处理
│   ├── utils.py           # 工具函数
│   ├── database.py       # 数据库
│   ├── resolve.py         # DNS 解析
│   └── ...
├── modules/                # 功能模块
│   ├── collect.py         # 收集调度器
│   ├── brute.py           # 爆破模块
│   ├── export.py          # 导出模块
│   ├── search/            # 搜索引擎
│   ├── certificates/      # 证书查询
│   ├── datasets/          # 数据集
│   └── check/             # 存活检查
├── data/                   # 数据资源
└── tests/                  # 单元测试
```

---

## 后续工作

### 扩展功能 (待实现)
- [ ] 更多搜索引擎模块 (Google, FOFA)
- [ ] 子域置换模块 (altdns)
- [ ] 子域接管检测
- [ ] 端口扫描

### 优化 (待实现)
- [ ] 异步支持 (asyncio)
- [ ] 并发执行优化
- [ ] 结果数据库存储

---

*最后更新: 2026-05-11*
*累计完成: 203 个测试*