# JustOne 项目实现指导

> 基于 JustOne构想.md 的详细实施指南
> 目标: 适配 Python 3.14.2 的子域名收集工具

---

## 1. 项目初始化

### 1.1 创建项目结构

```bash
# 创建项目目录
mkdir JustOne
cd JustOne

# 创建目录结构
mkdir -p config common modules/collect modules/search modules/datasets modules/certificates modules/check modules/dnsquery modules/intelligence modules/brute modules/export data results
```

### 1.2 初始化 Python 环境

```bash
# 使用 Python 3.14 创建虚拟环境
python3.14 -m venv venv

# 激活虚拟环境 (Linux/Mac)
source venv/bin/activate

# 激活虚拟环境 (Windows)
venv\Scripts\activate

# 安装核心依赖
pip install dnspython requests tqdm loguru

# 安装新依赖
pip install typer rich aiohttp pydantic
```

### 1.3 创建 requirements.txt

```
dnspython==2.6.1
requests==2.31.0
tqdm==4.66.1
loguru==0.7.2
typer==0.12.5
rich==13.7.0
aiohttp==3.9.1
pydantic==2.5.3
```

---

## 2. 项目框架结构

### 2.1 目录结构

```
JustOne/
├── justone.py                 # Typer CLI 主入口
├── requirements.txt           # Python 依赖
│
├── config/                    # 配置模块
│   ├── __init__.py           # 配置导出
│   ├── settings.py           # Pydantic 配置
│   └── logging.py            # 日志系统
│
├── common/                    # 公共模块
│   ├── __init__.py           # 模块导出
│   ├── domain.py             # 域名处理
│   ├── utils.py              # 工具函数
│   ├── database.py           # 数据库操作
│   ├── resolve.py            # DNS 解析
│   ├── records.py            # DNS 记录
│   ├── tldextract.py         # TLD 提取
│   ├── similarity.py         # 相似度计算
│   ├── module.py             # 模块基类
│   └── ipreg.py              # IP 注册信息
│
├── modules/                   # 功能模块
│   ├── __init__.py
│   ├── collect.py            # 收集调度器
│   ├── brute.py              # 爆破模块
│   ├── export.py             # 导出模块
│   ├── search/               # 搜索引擎模块
│   │   ├── __init__.py
│   │   ├── baidu.py
│   │   ├── bing.py
│   │   ├── google.py
│   │   └── fofa_api.py
│   ├── datasets/             # 数据集查询
│   │   ├── __init__.py
│   │   └── leakix.py
│   ├── certificates/         # 证书查询
│   │   ├── __init__.py
│   │   └── crtsh.py
│   ├── check/                # 子域验证
│   │   ├── __init__.py
│   │   ├── http.py
│   │   └── dns.py
│   ├── dnsquery/             # DNS 查询
│   │   ├── __init__.py
│   │   └── mx.py
│   └── intelligence/         # 威胁情报
│       └── __init__.py
│
├── data/                      # 数据资源
│   ├── subnames.txt
│   ├── subnames_medium.txt
│   ├── altdns_wordlist.txt
│   └── public_suffix_list.dat
│
└── results/                   # 结果输出目录
    ├── justone.db
    └── justone.log
```

---

## 3. 第一阶段: 核心框架搭建

### 3.1 配置系统 (config/)

#### config/__init__.py

```python
"""JustOne 配置模块"""

from config.settings import Settings, settings
from config.logging import init_logging

__all__ = ['Settings', 'settings', 'init_logging']
```

#### config/settings.py

```python
"""
JustOne 配置系统
基于 Pydantic 的现代化配置管理
"""

from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional


class HTTPConfig(BaseModel):
    timeout: int = 27
    verify_ssl: bool = False
    allow_redirect: bool = True
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    enable_random_ua: bool = True


class ProxyConfig(BaseModel):
    enable: bool = False
    pool: list[dict] = Field(default_factory=lambda: [
        {"http": "http://127.0.0.1:10808", "https": "https://127.0.0.1:10808"}
    ])


class BruteConfig(BaseModel):
    concurrent: int = 2000
    wordlist: Optional[Path] = None
    recursive: bool = False
    recursive_depth: int = 2


class CollectConfig(BaseModel):
    enabled: bool = True
    module_timeout: int = 300
    max_concurrent: int = 50
    save_module_result: bool = False


class Settings(BaseModel):
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = Path(__file__).parent.parent / "data"
    results_dir: Path = Path(__file__).parent.parent / "results"

    http: HTTPConfig = Field(default_factory=HTTPConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    brute: BruteConfig = Field(default_factory=BruteConfig)
    collect: CollectConfig = Field(default_factory=CollectConfig)

    enable_brute: bool = True
    enable_search: bool = True
    enable_datasets: bool = True
    enable_certificates: bool = True


settings = Settings()
```

#### config/logging.py

```python
"""
JustOne 日志系统
基于 loguru，兼容 Typer CLI
"""

import sys
from pathlib import Path
from loguru import logger


def init_logging(debug: bool = False):
    project_root = Path(__file__).parent.parent
    log_path = project_root / "results" / "justone.log"

    logger.remove()

    level = "DEBUG" if debug else "INFO"
    fmt = (
        "<green>{time:HH:mm:ss}</green> "
        "[<level>{level: <5}</level>] "
        "<cyan>{message}</cyan>"
    )

    logger.add(sys.stderr, level=level, format=fmt)
    logger.add(
        log_path,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="7 days"
    )

    return logger
```

---

### 3.2 公共模块 (common/)

#### common/__init__.py

```python
"""JustOne 公共模块"""

from common.domain import Domain
from common.utils import match_subdomains
from common.resolve import DNSResolver

__all__ = ['Domain', 'match_subdomains', 'DNSResolver']
```

#### common/domain.py

```python
"""
域名处理模块
"""

import re
from urllib.parse import urlparse


class Domain:
    """域名处理类"""

    def __init__(self, string: str):
        self.string = str(string)
        self.regexp = r'\b((?=[a-z0-9-]{1,63}\.)(xn--)?[a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,63}\b'
        self.domain = None

    def match(self) -> str | None:
        """匹配域名"""
        result = re.search(self.regexp, self.string, re.I)
        if result:
            return result.group()
        return None

    def extract(self):
        """提取域名各部分"""
        from common import tldextract
        data_dir = Path(__file__).parent.parent / "data"
        cache_file = data_dir / 'public_suffix_list.dat'
        ext = tldextract.TLDExtract(cache_file)
        result = self.match()
        if result:
            return ext(result)
        return None

    def registered(self) -> str | None:
        """获取注册域"""
        result = self.extract()
        if result:
            return result.registered_domain
        return None


from pathlib import Path
```

#### common/utils.py

```python
"""
工具函数模块
"""

import re
from urllib.parse import urlparse


def match_subdomains(domain: str, html: str, distinct: bool = True, fuzzy: bool = True) -> set:
    """
    使用正则表达式从响应中匹配子域名

    参数:
        domain: 主域名
        html: 响应HTML文本
        distinct: 是否去重 (默认True)
        fuzzy: 是否模糊匹配 (默认True)

    返回:
        set: 子域名集合
    """
    if fuzzy:
        regexp = r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.){0,}' \
                 + domain.replace('.', r'\.')
        result = re.findall(regexp, html, re.I)
        if not result:
            return set()
        deal = map(lambda s: s.lower(), result)
        if distinct:
            return set(deal)
        else:
            return list(deal)
    else:
        regexp = r'(?:\>|\"|\'|\=|\,)(?:http\:\/\/|https\:\/\/)?' \
                 r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.){0,}' \
                 + domain.replace('.', r'\.')
        result = re.findall(regexp, html, re.I)
    if not result:
        return set()
    regexp = r'(?:http://|https://)'
    deal = map(lambda s: re.sub(regexp, '', s[1:].lower()), result)
    if distinct:
        return set(deal)
    else:
        return list(deal)
```

#### common/module.py

```python
"""
模块基类
"""

import time
from typing import Optional


class Module:
    """收集模块基类"""

    def __init__(self, domain: str, config: Optional[dict] = None):
        self.module = 'BaseModule'
        self.source = 'BaseModule'
        self.domain = domain
        self.config = config or {}

        self.timeout = self.config.get('timeout', 27)
        self.verify = self.config.get('verify', False)

        self.subdomains = set()
        self.infos = dict()
        self.results = []

        self.start = time.time()
        self.end = None
        self.elapse = None

    def begin(self):
        """模块开始"""
        pass

    def finish(self):
        """模块结束"""
        self.end = time.time()
        self.elapse = round(self.end - self.start, 1)

    def run(self):
        """子类必须实现此方法"""
        raise NotImplementedError
```

---

### 3.3 CLI入口 (justone.py)

```python
"""
JustOne 主程序
基于 Typer 的现代化 CLI
"""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(help="JustOne - 强大的子域名收集工具")
console = Console()


@app.command()
def main(
    target: str = typer.Argument(..., help="目标域名"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出路径"),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式 (csv/json)"),
    brute: bool = typer.Option(True, "--brute/--no-brute", help="启用爆破模块"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """
    收集目标域名的子域名
    """
    from config.logging import init_logging
    init_logging(debug=verbose)

    console.print(f"[bold green]JustOne[/bold green] 开始收集子域名: {target}")

    from modules.collect import Collect
    from common.domain import Domain

    domain_obj = Domain(target)
    main_domain = domain_obj.registered()

    if not main_domain:
        console.print("[bold red]错误:[/bold red] 无法解析目标域名")
        raise typer.Exit(1)

    collector = Collect(main_domain)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("收集子域名中...", total=None)
        results = collector.run()
        progress.update(task, completed=100)

    console.print(f"[bold green]完成![/bold green] 共发现 {len(results)} 个子域名")

    if output:
        from modules.export import export_results
        export_results(results, output, format)
        console.print(f"结果已保存到: {output}")


@app.command()
def version():
    """显示版本信息"""
    console.print("JustOne v1.0.0")
    console.print("Python 3.14+")


if __name__ == "__main__":
    app()
```

---

## 4. 第二阶段: 功能模块框架

### 4.1 收集调度器 (modules/collect.py)

```python
"""
收集调度器
"""

from pathlib import Path
from typing import Optional


class Collect:
    """子域收集调度器"""

    def __init__(self, domain: str, config: Optional[dict] = None):
        self.domain = domain
        self.config = config or {}
        self.results = []

    def run(self):
        """运行收集"""
        # TODO: 实现收集逻辑
        pass

    def collect_search(self):
        """搜索引擎收集"""
        # TODO: 实现搜索引擎模块收集
        pass

    def collect_datasets(self):
        """数据集查询"""
        # TODO: 实现数据集模块收集
        pass

    def collect_certificates(self):
        """证书查询"""
        # TODO: 实现证书模块收集
        pass
```

### 4.2 模块结构模板

#### modules/search/__init__.py

```python
"""搜索引擎模块"""

__all__ = []
```

#### modules/search/baidu.py

```python
"""
百度搜索引擎模块
"""

from common.module import Module


class BaiduSearch(Module):
    """百度搜索子域收集"""

    def __init__(self, domain: str, config: dict = None):
        super().__init__(domain, config)
        self.module = 'BaiduSearch'
        self.source = 'baidu.com'

    def run(self):
        """执行百度搜索收集"""
        # TODO: 实现具体逻辑
        return []


def run(domain: str, config: dict = None):
    """模块执行入口"""
    module = BaiduSearch(domain, config)
    module.begin()
    results = module.run()
    module.finish()
    return results
```

#### 其他模块使用相同模板结构

---

### 4.3 爆破模块框架 (modules/brute.py)

```python
"""
子域爆破模块
"""


class Brute:
    """子域暴力猜测"""

    def __init__(self, domain: str, config: dict = None):
        self.domain = domain
        self.config = config or {}

    def run(self):
        """执行爆破"""
        # TODO: 实现爆破逻辑
        return []

    def generate_candidates(self, wordlist: list) -> list:
        """生成候选子域"""
        # TODO: 实现候选生成
        pass
```

### 4.4 导出模块框架 (modules/export.py)

```python
"""
导出模块
"""

import csv
import json
from pathlib import Path
from typing import Any


def export_results(results: list, output: Path, format: str = 'csv'):
    """导出结果到文件"""
    output.parent.mkdir(parents=True, exist_ok=True)

    if format == 'json':
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    else:
        if results:
            headers = results[0].keys()
            with open(output, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(results)
```

---

## 5. 各模块详细规划 (待实现)

### 5.1 搜索引擎模块 (modules/search/)

| 模块 | 状态 | 说明 |
|------|------|------|
| baidu.py | 待实现 | 百度搜索 |
| bing.py | 待实现 | Bing搜索 |
| google.py | 待实现 | Google搜索 |
| fofa_api.py | 待实现 | FOFA API |
| hunter_api.py | 待实现 | 鹰图API |

### 5.2 证书查询模块 (modules/certificates/)

| 模块 | 状态 | 说明 |
|------|------|------|
| crtsh.py | 待实现 | crts.sh 查询 |
| certspotter.py | 待实现 | CertSpotter |

### 5.3 数据集查询模块 (modules/datasets/)

| 模块 | 状态 | 说明 |
|------|------|------|
| leakix.py | 待实现 | LeakIX |
| rapid7.py | 待实现 | Rapid7 FDNS |

### 5.4 子域验证模块 (modules/check/)

| 模块 | 状态 | 说明 |
|------|------|------|
| http.py | 待实现 | HTTP响应检查 |
| dns.py | 待实现 | DNS解析验证 |
| cdn.py | 待实现 | CDN识别 |

---

## 6. 使用示例

### 6.1 基本用法

```bash
# 收集子域名
python justone.py example.com

# 指定输出文件
python justone.py example.com -o results.csv

# 输出 JSON 格式
python justone.py example.com -o results.json --format json

# 禁用爆破模块
python justone.py example.com --no-brute

# 详细输出
python justone.py example.com -v
```

### 6.2 进阶用法

```python
# 编程方式使用
from modules.collect import Collect
from common.domain import Domain

domain = Domain('example.com')
main_domain = domain.registered()

collector = Collect(main_domain, config={'timeout': 30})
results = collector.run()

print(f"发现 {len(results)} 个子域名")
```

---

## 7. 开发注意事项

### 7.1 Python 3.14 兼容性

- 使用 `match` 语句需谨慎，确保逻辑正确
- 新语法特性可选择性使用
- 依赖包需验证 3.14 兼容性

### 7.2 性能优化

- 使用 `concurrent.futures` 或 `asyncio` 处理并发
- DNS 批量解析使用 `dnspython` 的 `resolve` 方法
- HTTP 请求使用连接池 (`requests.Session`)

### 7.3 代码质量

- 添加类型标注 (`typing`, `pydantic`)
- 保持模块独立性，减少耦合
- 完善的错误处理和日志记录

---

## 8. 实施计划

### Phase 1: 框架搭建 (本周)
- [ ] 项目目录结构
- [ ] 配置系统
- [ ] 日志系统
- [ ] CLI入口
- [ ] 模块基类
- [ ] 收集调度器框架
- [ ] 各模块模板

### Phase 2: 核心功能实现 (下周)
- [ ] 收集调度器实现
- [ ] 搜索引擎模块实现
- [ ] 证书查询模块实现
- [ ] 子域验证模块

### Phase 3: 扩展功能
- [ ] 爆破模块
- [ ] 导出功能
- [ ] 测试与优化

---

*文档基于 JustOne构想.md 编写*
*最后更新: 2026-05-08*