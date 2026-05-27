# JustOne 项目开发日志

## 2026-05-27 — 子域名接管检测模块

### 一、背景

子域名接管（Subdomain Takeover）是安全检测中重要一环。
当一个子域名的 CNAME 记录指向某外部服务（如 GitHub Pages、
AWS S3、Heroku 等），但该外部服务已被释放或未配置时，
攻击者可注册该服务并完成接管。

根据 JustOne构想.md §11规划，需要实现一个独立的子域名接管检测模块。

### 二、设计决策

| 决策 | 选择 |
|------|------|
| 模块组 | 独立 modules/takeover/，不继承 Module 基类 |
| 指纹格式 | JSON，支持 suffix/regex/contains 三种 CNAME 匹配 |
| 检测流程 | DNS CNAME → 指纹匹配 → HTTP 确认（双重确认）|
| 并发 | asyncio.Semaphore(20) |
| DNS 解析器 | 国内优先公共 DNS（223.5.5.5, 114.114.114.114, 1.1.1.1, 8.8.8.8）|
| 结果形式 | TakeoverResult dataclass（status/detail/service/cname/url）|
| NXDOMAIN | not_vulnerable（非 error）|
| 缓存 | @lru_cache CNAME 结果（1024条）|
| 输出格式 | 结构化输出（-J）或 Rich 表格 |

### 三、文件结构

―― modules/takeover/
│   __init__.py              # 导入保护
│   fingerprints.py         # 指纹加载 + CNAME 匹配
│   takeover.py             # 主逻辑
―― data/takeover_fingerprints.json   # 15 个服务指纹
―― tests/test_takeover.py           # 39 个单元测试

### 四、实施详情

#### 4.1 指纹模型（data/takeover_fingerprints.json）

每个服务指纹包含：
- cname: 匹配规则（suffix/regex/contains）
- service: 服务名称
- http: 确认目标（status/body 匹配）

预装 15 个高频服务：
GitHub Pages, Heroku, AWS S3, AWS CloudFront, Azure, DigitalOcean, Fastly,
Firebase, GitLab, Pantheon, ReadMe, Surge, Vercel, WordPress, Shopify

#### 4.2 指纹加载（fingerprints.py）

- load_fingerprints(): 读取 JSON 文件
- match_cname(): suffix/regex/contains 三种模式匹配
- find_matching_fingerprint(): 查找匹配的服务指纹

#### 4.3 主逻辑（takeover.py）

TakeoverCheck 类核心方法：
- _resolve_cname(): DNS CNAME 查询（@staticmethod @lru_cache）
- _process_dns_result(): 分类 CNAME 结果为 vulnerable/unknown/not_vulnerable
- _apply_http_check(): HTTP 确认（并行访问多个 path）
- _check_http_path(): 单个 HTTP 请求
- _check_fingerprint_match(): status + body 双重校验
- _judge(): 综合判定 status
- run(): asyncio.as_completed + tqdm 进度条

takeover_run(): CLI 入口，支持 target/-i/-o/-f/-c/――no-progress

#### 4.4 CLI 集成（justone.py）

takeover 子命令参数：
- TARGET: 目标域名
- -i/--input: 子域名文件
- -o/--output: 输出文件
- -f/--format: 输出格式（json/csv/txt）
- -c/--concurrent: 并发数
- --fingerprint-file: 自定义指纹文件
- --skip-brute: 跳过暴力析解
- --no-progress: 隐藏进度条

### 五、问题与修复

#### 5.1 问题一：进度条卡在 0

状态：已修复

发现时间：2026-05-27 上午（首次运行 takeover 命令时）

表现：进度条永远显示 0/1494，无任何子域名完成检测

根因：在  内直接调用同步 ，
该函数内部  是同步阻塞调用，直接卡住了
asyncio 事件循环线程，导致所有协程无法推进。
尽管设了 Semaphore(20)，实际为串行执行。

修复：
- 将 DNS 查询通过  抛到线程池
- 加  超时保护
- DNS 超时时等 2s 重试一次

#### 5.2 问题二：大面积 DNS 超时

状态：已修复

表现：1494 个子域名中 1491 个为 TIMEOUT（99.8%）

根因：
1. 默认使用系统 DNS 解析器，国内网络环境下往往通过本地运营商 DNS
2. 20 路并发压垮解析器速率限制
3. 没有重试机制，一次超时即放弃

修复：
- 指定国内优先公共 DNS（AliDNS 223.5.5.5, 114DNS 等）
- TIMEOUT 时等 2s 重试一次
- res.lifetime = 20s 给多个 nameserver 串联时间

### 六、测试结果

pytest tests/test_takeover.py: 39 passed
pytest 全量: 309 passed, 7 skipped（7 跳过为 API key 缺失，属正常）
全量 0 warning（除 PydanticDeprecatedSince20 警告）

### 七、已知问题

1. DNS 超时重试会延长检测时间（每个超时多 2s）
2. 指纹库仅15个服务，可按需扩展
3. HTTP 确认只支持 status/body 检查，不支持 header 检查
4. censys.io 请求失败问题仍未解决（原有已知问题）
