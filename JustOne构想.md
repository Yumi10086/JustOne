JustOne构想 (适配Python 3.14.2)

## 1. 核心设计要求

1. 从响应中匹配子域名采用**`urllib.parse` + 白名单** 对标"match_subdomains"
2. 命令行接口用 **Typer**
3. 进度条用 **tqdm**
4. 多线程 + 异步支持 (asyncio)
5. 模仿OneForAll的优点，如功能模块化，方便添加删除及自定义

---

## 2. 模块继承关系

### 2.1 可以直接搬运的模块 (无需修改)

| 模块 | 路径 | 说明 |
|------|------|------|
| **match_subdomains** | common/utils.py:643-677 | 子域名正则匹配算法，构想已明确采用此逻辑 |
| **Domain类** | common/domain.py | 域名解析、提取、注册域匹配 |
| **tldextract** | common/tldextract.py | TLD提取，基于public_suffix_list |
| **resolve** | common/resolve.py | DNS批量解析 (dnspython) |
| **records** | common/records.py | DNS记录处理 (A/CNAME/MX等) |
| **similarity** | common/similarity.py | 字符串相似度计算 |
| **ipreg.py** | common/ipreg.py | IP注册信息查询 |
| **ipasn.py** | common/ipasn.py | ASN查询 |
| **data/** | data/ | 子域名字典、CDN指纹等数据资源 |

**搬运说明**: 这些模块功能独立，不依赖特定CLI框架，可直接复用。

---

### 2.2 需要修改后搬运的模块

| 模块 | 路径 | 修改建议 |
|------|------|----------|
| **module.py** | common/module.py | 基类保留，但需移除对config.settings的强依赖，改用依赖注入；将日志改为可选参数 |
| **database.py** | common/database.py | 保留SQLite操作逻辑，但需简化表结构；移除对records库的依赖，直接用sqlite3 |
| **utils.py** | common/utils.py | 保留核心工具函数(match_subdomains, dns_query等)，移除check_dep版本检查(改为3.14+)，移除对fire的依赖 |
| **request.py** | common/request.py | 保留requests核心逻辑，但移除对settings的依赖，改为参数传入 |
| **config/setting.py** | config/setting.py | 大幅精简，保留必要的超时、代理、UA等配置，改用dataclass或Pydantic定义 |
| **config/log.py** | config/log.py | 保留loguru，但简化配置，可与Typer兼容 |
| **domain.py** | common/domain.py | 保留核心逻辑，但移除对settings的依赖 |

**修改原则**: 
- 解除对全局settings的强依赖，改为参数/依赖注入
- 移除版本检查(OneForAll要求3.6+，JustOne只需支持3.14+)
- 保持功能逻辑，移除CLI相关代码

---

### 2.3 需要重新写的模块

| 模块 | 说明 | 重新写的理由 |
|------|------|--------------|
| **CLI入口** | Typer主入口 | OneForAll使用fire，JustOne要用Typer实现现代化CLI |
| **收集调度器** | modules/collect.py | 需要适配新的模块结构和异步支持 |
| **brute.py** | 子域爆破 | 需要完全重写以适配新架构和async |
| **takeover.py** | 子域接管检测 | 重写以适配新CLI和数据结构 |
| **export.py** | 数据导出 | 重写，简化导出格式 |
| **modules/finder.py** | 子域发现器 | 重写以适配新架构 |
| **modules/altdns.py** | 子域置换 | 可参考逻辑但需重写 |
| **modules/enrich.py** | 信息丰富 | 重写，简化逻辑 |
| **配置文件结构** | config/*.py | 完全重构，采用更现代的配置方式(Pydantic) |

**重新编写的原因**:
- 这些模块深度耦合了OneForAll的CLI框架(fire)和配置系统
- 需要适配新的Typer CLI和数据流
- Python 3.14有新的语法特性可用

---

## 3. 数据结构设计

### 3.1 子域结果结构 (可直接复用)

```python
SubdomainResult = {
    'subdomain': str,      # 子域名
    'domain': str,         # 主域名
    'resolve': int,        # 是否解析成功 (0/1)
    'alive': int,          # 是否存活 (0/1)
    'ip': str,             # IP地址
    'cname': str,          # CNAME
    'port': int,           # 端口
    'level': int,          # 子域层级
    'cdn': int,            # 是否CDN
    'module': str,         # 发现模块
    'source': str,         # 数据源
}
```

---

## 4. 依赖包对比

### 4.1 OneForAll原有依赖 (需筛选)

```
beautifulsoup4==4.11.1  # 可选，网页解析
dnspython==2.2.1        # 保留，DNS解析
requests==2.28.1         # 保留，HTTP请求
tqdm==4.64.0             # 保留，进度条
SQLAlchemy==1.3.22       # 可不装，改用sqlite3
tenacity==8.0.1          # 可不装，用asyncio重试
loguru==0.6.0            # 保留，日志
Pysocks==1.7.1           # 可选，代理
```

### 4.2 JustOne新增依赖

```
typer>=0.12.0            # CLI框架 (新增)
rich>=13.0.0             # 终端美化 (可选，配合typer)
aiohttp>=3.9.0           # 异步HTTP (新增)
asyncio-throttle>=1.0.0  # 异步限流 (新增)
pydantic>=2.0.0          # 配置验证 (推荐)
```

**注意**: Python 3.14兼容性检查需在后续测试验证。

---

## 5. 目录结构建议

```
JustOne/
├── justone.py              # Typer主入口
├── config/
│   ├── __init__.py
│   ├── settings.py         # 精简配置
│   └── logging.py          # 日志配置
├── common/                 # 公共模块 (大部分直接搬运)
│   ├── utils.py
│   ├── domain.py
│   ├── database.py
│   ├── resolve.py
│   ├── records.py
│   ├── tldextract.py
│   └── similarity.py
├── modules/                # 收集模块 (需重写调度逻辑)
│   ├── collect.py
│   ├── search/
│   ├── datasets/
│   └── certificates/
├── data/                  # 数据资源 (直接搬运)
│   ├── subnames.txt
│   └── public_suffix_list.dat
└── results/               # 结果输出
```

---

## 6. 实施优先级

### Phase 1: 基础设施 (直接搬运 + 简单修改)
1. 配置系统简化
2. 公共模块迁移 (utils, domain, tldextract, records)
3. 数据库模块简化

### Phase 2: 核心功能 (修改后搬运)
4. 模块基类适配
5. HTTP请求封装
6. 子域匹配逻辑

### Phase 3: CLI与调度 (重新写)
7. Typer CLI入口
8. 收集调度器重写
9. 进度条集成

### Phase 4: 扩展功能 (重新写/参考)
10. 爆破模块重写
11. 导出功能重写
12. 测试与优化

---

## 7. 注意事项

1. **Python 3.14兼容性**: 需测试所有依赖包的兼容性
2. **异步支持**: 考虑在收集模块中加入asyncio支持
3. **类型标注**: 建议使用typing和Pydantic增加类型安全
4. **日志与CLI集成**: loguru可与Typer很好配合

---

## 8. 模块详细设计

### 8.1 搜索引擎模块 (modules/search/)

| 模块 | 描述 | 优先级 |
|------|------|--------|
| baidu.py | 百度搜索 | 高 |
| bing.py | Bing搜索 | 高 |
| google.py | Google搜索 | 高 |
| so.py | 搜狗搜索 | 中 |
| yahoo.py | Yahoo搜索 | 中 |
| fofa_api.py | FOFA API | 高 |
| hunter_api.py | 鹰图API | 高 |
| shodan_api.py | Shodan API | 中 |
| zoomeye_api.py | ZoomEye API | 中 |

**设计要点**:
- 使用 `urllib.parse` 构建搜索URL
- 使用白名单机制匹配子域名
- 支持异步请求 (aiohttp)
- 支持分页抓取

### 8.2 证书查询模块 (modules/certificates/)

| 模块 | 描述 | 优先级 |
|------|------|--------|
| crtsh.py | crts.sh 查询 | 高 |
| certspotter.py | CertSpotter | 中 |
| google.py | Google CT | 中 |
| censys_api.py | Censys API | 低 |

### 8.3 数据集查询模块 (modules/datasets/)

| 模块 | 描述 | 优先级 |
|------|------|--------|
| leakix.py | LeakIX 数据集 | 中 |
| rapid7.py | Rapid7 FDNS | 高 |

### 8.4 DNS查询模块 (modules/dnsquery/)

| 模块 | 描述 | 优先级 |
|------|------|--------|
| mx.py | MX记录查询 | 中 |
| ns.py | NS记录查询 | 低 |
| txt.py | TXT记录查询 | 低 |
| dnszone.py | DNS区域传输 | 低 |

### 8.5 子域验证模块 (modules/check/)

| 模块 | 描述 | 优先级 |
|------|------|--------|
| httpx.py | HTTP响应检查 | 高 |
| dns.py | DNS解析验证 | 高 |
| cdn.py | CDN识别 | 中 |

---

## 9. 异步架构设计

### 9.1 异步请求层

```python
# common/async_request.py
import asyncio
import aiohttp
from typing import Optional


class AsyncRequest:
    """异步HTTP请求封装"""
    
    def __init__(self, timeout: int = 27, max_retries: int = 3):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def get(self, url: str, **kwargs) -> Optional[aiohttp.ClientResponse]:
        for _ in range(self.max_retries):
            try:
                async with self.session.get(url, **kwargs) as resp:
                    if resp.status == 200:
                        return await resp.text()
            except Exception:
                await asyncio.sleep(1)
        return None
```

### 9.2 异步收集器

```python
# modules/async_collector.py
import asyncio
from typing import Optional


class AsyncCollector:
    """异步子域收集器"""
    
    def __init__(self, domain: str, max_concurrent: int = 50):
        self.domain = domain
        self.max_concurrent = max_concurrent
        self.results = set()
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def collect_from_module(self, module_func):
        """从单个模块异步收集"""
        async with self.semaphore:
            result = await module_func(self.domain)
            self.results.update(result)
    
    async def run(self, modules: list):
        """运行所有模块"""
        tasks = [self.collect_from_module(mod) for mod in modules]
        await asyncio.gather(*tasks)
        return list(self.results)
```

---

## 10. 数据流程设计

### 10.1 主流程

```
┌─────────────┐
│   输入域名   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  域名解析/标准化  │
│  (Domain类)     │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│   模块调度器     │
│  (Collect类)    │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  并发执行模块    │
│ (search/datasets│
│  /certificates) │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  子域匹配/去重    │
│ (match_subdomains)│
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  子域验证        │
│  (DNS/HTTP)    │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  结果存储/导出   │
│  (DB/CSV/JSON) │
└─────────────────┘
```

### 10.2 数据结构

```python
# 子域收集结果
class SubdomainResult:
    subdomain: str          # 子域名 (如 sub.example.com)
    domain: str            # 主域名 (如 example.com)
    resolve: int           # DNS解析状态 (0/1)
    alive: int             # HTTP存活状态 (0/1)
    ip: str                # IP地址 (多个用逗号分隔)
    cname: str             # CNAME记录
    port: int              # 端口号
    level: int             # 子域层级
    cdn: int               # 是否CDN (0/1)
    module: str            # 发现模块名称
    source: str            # 数据源
    created_at: datetime   # 发现时间
```

---

## 11. 错误处理机制

### 11.1 模块级错误处理

```python
class Module:
    """带错误处理的模块基类"""
    
    def run(self):
        try:
            # 模块逻辑
            pass
        except Exception as e:
            logger.warning(f"模块 {self.module} 执行失败: {e}")
            return []
    
    def handle_error(self, error: Exception) -> None:
        """统一错误处理"""
        error_type = type(error).__name__
        logger.debug(f"错误类型: {error_type}, 错误信息: {error}")
```

### 11.2 重试机制

```python
# 使用 tenacity 或自定义重试
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_with_retry(session, url):
    async with session.get(url) as resp:
        return await resp.text()
```

---

## 12. 配置分层设计

### 12.1 配置优先级

1. **命令行参数** (最高优先级)
2. **环境变量** (次优先级)
3. **配置文件** (次优先级)
4. **默认值** (最低优先级)

### 12.2 配置项分类

```python
# 配置分类
HTTP_CONFIG = {
    'timeout': 27,
    'verify_ssl': False,
    'allow_redirects': True,
    'user_agent': 'Mozilla/5.0...',
    'proxy': None,
}

BRUTE_CONFIG = {
    'enabled': True,
    'concurrent': 2000,
    'wordlist': 'data/subnames.txt',
    'recursive': False,
    'depth': 2,
}

COLLECT_CONFIG = {
    'enabled_modules': ['search', 'datasets', 'certificates'],
    'module_timeout': 300,
    'save_all_results': False,
}
```

---

## 13. 项目阶段规划

### Phase 1: 基础框架搭建 (1-2周)
- [ ] 项目初始化 (Python 3.14环境)
- [ ] 配置系统 (Pydantic)
- [ ] 日志系统 (loguru)
- [ ] 公共模块 (domain, utils, resolve, tldextract)
- [ ] 模块基类 (Module)

### Phase 2: 核心功能实现 (2-3周)
- [ ] Typer CLI入口
- [ ] 收集调度器
- [ ] 子域匹配逻辑
- [ ] 子域验证模块
- [ ] 数据库模块

### Phase 3: 收集模块实现 (3-4周)
- [ ] 搜索引擎模块 (baidu, bing, google)
- [ ] 证书查询模块 (crtsh)
- [ ] 数据集查询模块
- [ ] DNS查询模块

### Phase 4: 扩展功能 (2-3周)
- [ ] 子域爆破模块
- [ ] 子域置换模块
- [ ] 子域接管检测
- [ ] 结果导出

### Phase 5: 优化与测试 (1-2周)
- [ ] 性能优化
- [ ] 异步支持
- [ ] 单元测试
- [ ] 集成测试

---

## 14. 代码规范建议

### 14.1 命名规范
- **模块**: 小写字母，下划线分隔 (如 `baidu_search.py`)
- **类**: 大驼峰命名 (如 `Domain`)
- **函数**: 小写字母，下划线分隔 (如 `match_subdomains`)
- **常量**: 全大写，下划线分隔 (如 `DEFAULT_TIMEOUT`)

### 14.2 类型标注
```python
def match_subdomains(domain: str, html: str, distinct: bool = True) -> set[str]:
    """从HTML中匹配子域名"""
    ...

class Collect:
    def run(self) -> list[dict[str, Any]]:
        ...
```

### 14.3 文档字符串
```python
def resolve(domain: str, qtype: str = 'A') -> list[str]:
    """
    解析域名DNS记录
    
    Args:
        domain: 要解析的域名
        qtype: DNS记录类型 (A/CNAME/MX/TXT)
    
    Returns:
        解析结果列表，解析失败返回空列表
    
    Raises:
        DNSException: DNS解析异常
    """
```

---

*最后更新: 2026-05-08*---

