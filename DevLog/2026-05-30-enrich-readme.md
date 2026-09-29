# JustOne 项目开发日志

## 2026-05-30 — 信息丰富模块 (enrich) + README 同步

### 一、新增信息丰富模块 (enrich)

基于已有 SQLite 数据库结果，提供三阶段信息补全管道：

| 阶段 | 内容 | 方式 |
|------|------|------|
| 1. DNS 解析 | 线程池并行解析，补全 IP、CNAME | concurrent.futures |
| 2. HTTP 探测 | IP 直连 + Host 头，获取状态码、标题、响应头 Banner | aiohttp 异步并发 |
| 3. IP 定位 | CDN IP CIDR 匹配、ASN/ORG/CIDR 查询 | 本地无网络，IPAsnInfo + cdn_ip_cidr.json |

**涉及文件:**
- modules/enrich.py — 核心实现 (341 行)
- justone.py — 注册 enrich CLI 命令
- .gitignore — 配套修改

**CLI 接口:**

    python justone.py enrich <db_path>
    python justone.py enrich <db_path> -t <table_name>
    python justone.py enrich <db_path> -c <concurrency>

### 二、README.md 同步

根据新模块更新文档：

- 功能列表新增「信息丰富」条目
- 使用说明新增 enrich 命令章节及示例
- 输出文件名表新增 enrich 行
- 模块架构图新增 enrich.py
- 数据源表新增「IP 定位」和「信息丰富」两行
- 测试用例数 340+ → 350+

### 三、备注

- AGENTS.md 中的架构说明、模块注册方式等无需修改（enrich 不走 collect.py 注册流程，是独立 CLI 命令）
- 无新 API key 依赖，所有数据源均为本地分析或已有基础设施
