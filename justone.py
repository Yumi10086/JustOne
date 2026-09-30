#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JustOne - 子域名收集工具
=========================

一、基本收集
    python justone.py main example.com                    # 完整收集（搜索+证书+数据集+爆破+置换）
    python justone.py main example.com --no-brute        # 禁用爆破模块
    python justone.py main example.com --no-altdns       # 禁用子域置换模块
    python justone.py main example.com --no-search       # 禁用搜索引擎模块
    python justone.py main example.com --no-cert         # 禁用证书查询模块
    python justone.py main example.com --no-dataset      # 禁用数据集查询模块
    python justone.py main example.com --save-db         # 模块结果写入 SQLite（供 enrich 命令使用）
    python justone.py main example.com --enrich          # 收集后自动补全 DNS/HTTP/CDN/IP（额外输出 enrich_域名.csv）
    python justone.py main -i targets.txt                # 批量收集多个域名（结果按域名各自输出）

二、仅执行爆破
    python justone.py brute example.com                   # 使用默认字典爆破
    python justone.py brute example.com -c 1000          # 设置并发数
    python justone.py brute example.com -w wordlist.txt  # 指定字典文件
    python justone.py brute example.com --auth-ns        # 使用目标权威 NS 解析（更快）

三、子域置换扩展
    python justone.py altdns example.com                  # 自动收集+爆破后置换
    python justone.py altdns example.com -i subdomains.txt # 从已知子域名文件直接置换
    python justone.py altdns example.com --no-number     # 禁用数字追加置换规则

四、检查存活状态 & DNS安全
    python justone.py check example.com                  # HTTP 存活检查（默认排除泛解析域名）
    python justone.py check example.com --dns            # 仅 DNS 检查
    python justone.py check example.com --dns-security   # 执行 DNS 安全检测（DNSSEC/投毒/劫持）
    python justone.py check -i subdomains.txt             # 从文件批量检查
    python justone.py check -i subdomains.txt -f txt     # 指定输出格式
    python justone.py check example.com --no-wildcard    # 关闭泛解析检测与排除
    python justone.py check example.com --wildcard-cidr  # 泛解析按同 /24 网段匹配

五、子域接管检测
    python justone.py takeover example.com                # 检测子域名接管风险
    python justone.py takeover -i subdomains.txt          # 从文件批量检测

六、输出选项
    -o, --output PATH      指定输出文件路径（默认: results/目录）
    -f, --format FORMAT   输出格式: csv/json/txt（默认: csv）

    # 默认输出到 results/ 目录，自动添加功能前缀:
    #   main 命令    -> results/collect_域名.csv
    #   brute 命令   -> results/brute_域名.csv
    #   altdns 命令  -> results/altdns_域名.csv
    #   check 命令   -> results/check_域名.csv
    #   takeover 命令 -> results/takeover_域名.csv

七、泛解析（Wildcard DNS）
    多随机标签探测 *.域名 是否存在泛解析，并过滤解析到泛解析 IP/CNAME 的假阳性结果。
    main / brute / altdns 均默认启用，可用 --no-wildcard 关闭：
        python justone.py main example.com --no-wildcard        # 禁用泛解析检测与过滤
        python justone.py main example.com --wildcard-cidr      # 泛解析按同 /24 网段匹配（应对轮换 IP）
        python justone.py brute example.com --no-wildcard
        python justone.py altdns example.com --wildcard-cidr

八、其他
    python justone.py --version                          # 查看版本
    python justone.py --help                             # 查看帮助
    python justone.py main --help                        # 查看 main 命令帮助
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional, Set

import typer
from rich.console import Console

from config.logging import init_logging
from config.settings import settings
from modules.collect import Collect, set_collect_config
from modules.brute import Brute, set_brute_config
from modules.altdns import Altdns, set_altdns_config
from modules.enrich import Enrich
from modules.export import export_subdomains, export_results
from modules.takeover import takeover_run
from common.domain import Domain
from common import utils
from common import resolve

# 初始化全局 HTTP 配置（代理等）
utils.set_http_config(
    timeout=settings.http_timeout,
    verify_ssl=settings.http_verify_ssl,
    enable_random_ua=settings.http_enable_random_ua,
    proxy_enable=settings.proxy_enable,
    proxy_pool=settings.get_proxy_list(),
)

# 初始化 SOCKS5 DNS 代理（使 DNS 爆破等走代理绕过 GFW 污染）
resolve.init_dns_proxy(settings.get_proxy_list())

# 将 settings 中的配置注入各模块全局配置（泛解析检测/过滤等）
set_brute_config({
    'concurrent': settings.brute_concurrent,
    'recursive': settings.brute_recursive,
    'recursive_depth': settings.brute_recursive_depth,
    'recursive_max_fanout': settings.brute_recursive_max_fanout,
    'recursive_max_candidates': settings.brute_recursive_max_candidates,
    'wildcard_check': settings.brute_wildcard_check,
    'wildcard_deal': settings.brute_wildcard_deal,
    'wildcard_probes': settings.wildcard_probes,
    'wildcard_cidr': settings.wildcard_cidr,
})
set_altdns_config({
    'wildcard_check': settings.brute_wildcard_check,
    'wildcard_deal': settings.brute_wildcard_deal,
    'wildcard_probes': settings.wildcard_probes,
    'wildcard_cidr': settings.wildcard_cidr,
})
set_collect_config({
    'wildcard_filter': settings.brute_wildcard_check,
    'wildcard_probes': settings.wildcard_probes,
    'wildcard_cidr': settings.wildcard_cidr,
})


__version__ = "1.0.0"

app = typer.Typer(
    help="JustOne - 强大的子域名收集工具",
    add_completion=False,
)
console = Console()


def get_default_output(domain: str, prefix: str = '', format: str = 'csv') -> Path:
    """生成默认输出路径"""
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{prefix}_" if prefix else ""
    filename = f"{prefix}{domain}.{format}"
    return results_dir / filename


def load_subdomain_file(path: Path) -> Set[str]:
    """
    从 TXT/CSV 文件加载子域名集合（自动识别格式）

    CSV 需含表头，优先取 subdomain/domain/url/host 列，未命中则取第一列；
    TXT 每行一个子域名，空行与 # 开头的注释行会被忽略。

    :param Path path: 输入文件路径
    :return: 子域名集合
    """
    import csv as csv_module

    subdomains: Set[str] = set()
    with open(path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
        f.seek(0)

        # 含逗号视为 CSV（多列），否则按纯文本处理（每行一个子域名）
        if ',' in first_line:
            reader = csv_module.DictReader(f)
            for row in reader:
                sub = (row.get('subdomain') or row.get('domain')
                       or row.get('url') or row.get('host'))
                if not sub:
                    # 未命中常见列名时回退到第一列
                    sub = next(iter(row.values()), None)
                if sub:
                    sub = str(sub).strip()
                    if sub and not sub.startswith('#'):
                        subdomains.add(sub)
        else:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    subdomains.add(line)
    return subdomains


def version_callback(value: bool):
    """显示版本信息"""
    if value:
        console.print(f"[bold green]JustOne[/bold green] v{__version__}")
        console.print("Python 3.14+")
        console.print("子域名收集工具")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", "-V", callback=version_callback, is_eager=True, help="显示版本"),
):
    """JustOne 子域名收集工具"""
    pass


def run_collect_pipeline(domain: str, config: dict, wildcard_config: dict, *,
                         brute: bool = True, altdns: bool = True,
                         disable_search: bool = False, disable_cert: bool = False,
                         disable_dataset: bool = False,
                         output: Optional[Path] = None, format: str = 'csv',
                         enrich: bool = False, enrich_concurrent: int = 100):
    """
    执行单个域名的完整收集流水线：收集 → 爆破 → 置换 → 导出 → 可选信息补全

    :param str domain: 注册域名
    :param dict config: 收集调度器配置
    :param dict wildcard_config: 泛解析配置
    :param bool brute: 是否执行爆破
    :param bool altdns: 是否执行子域置换
    :param bool disable_search: 是否禁用搜索引擎模块
    :param bool disable_cert: 是否禁用证书查询模块
    :param bool disable_dataset: 是否禁用数据集模块
    :param Path output: 输出文件路径，None 使用默认路径
    :param str format: 输出格式
    :param bool enrich: 是否执行信息补全（DNS/HTTP/CDN/IP）
    :param int enrich_concurrent: 信息补全并发数
    """
    console.print(f"[bold green]JustOne[/bold green] 开始收集子域名: [cyan]{domain}[/cyan]")

    subdomains = set()
    total_elapse = 0

    def show_progress(description: str, start_time: float):
        """单行进度显示"""
        elapsed = time.time() - start_time
        sys.stdout.write(f'\r  {description} [{elapsed:.1f}s]')
        sys.stdout.flush()

    if not (disable_search and disable_cert and disable_dataset):
        start = time.time()
        sys.stdout.write('  执行信息收集模块... ')
        sys.stdout.flush()
        collect = Collect(domain, config)
        subdomains = set(collect.run())
        total_elapse += collect.elapse or 0
        show_progress('完成', start)
        print()

    if brute:
        start = time.time()
        sys.stdout.write('  执行爆破模块... ')
        sys.stdout.flush()
        brute_module = Brute(domain, wildcard_config)
        brute_subdomains = brute_module.run()
        subdomains.update(brute_subdomains)
        total_elapse += brute_module.get_elapse() or 0
        show_progress('完成', start)
        print()

    if altdns and subdomains:
        start = time.time()
        sys.stdout.write('  执行子域置换... ')
        sys.stdout.flush()
        altdns_module = Altdns(domain, subdomains, wildcard_config)
        altdns_subdomains = altdns_module.run()
        subdomains.update(altdns_subdomains)
        total_elapse += altdns_module.get_elapse() or 0
        show_progress('完成', start)
        print()

    if not subdomains:
        console.print("\n[yellow]未发现子域名[/yellow]")
        return

    console.print(f"\n[bold green]完成![/bold green] 共发现 [yellow]{len(subdomains)}[/yellow] 个子域名")
    console.print(f"[dim]总耗时: {total_elapse:.1f} 秒[/dim]")

    if not output:
        output = get_default_output(domain, 'collect', format)
    if format == 'txt':
        export_subdomains(sorted(subdomains), output, 'txt')
    else:
        results = [{'subdomain': s} for s in sorted(subdomains)]
        export_results(results, output, format)
    console.print(f"[green]结果已保存到: {output}[/green]")

    if enrich:
        _enrich_domain(domain, enrich_concurrent, format)


def _enrich_domain(domain: str, concurrent: int, format: str):
    """
    对指定域名的 SQLite 记录执行信息补全，并导出全字段结果

    需先以 --save-db 收集（--enrich 会自动启用），
    导出文件为 results/enrich_<域名>.<格式>。

    :param str domain: 注册域名
    :param int concurrent: 补全并发数
    :param str format: 导出格式
    """
    db_file = Path(__file__).parent / 'results' / 'result.sqlite3'
    if not db_file.exists():
        console.print("[yellow]未找到 SQLite 数据库（results/result.sqlite3），跳过信息补全[/yellow]")
        return

    table = domain.replace('.', '_')
    console.print(f"[cyan]执行信息补全 (enrich): {table}[/cyan]")
    enricher = Enrich(str(db_file), concurrent=concurrent)
    try:
        enricher.load(table)
        if not enricher.records:
            console.print(f"[yellow]数据库中没有 {domain} 的记录，跳过补全[/yellow]")
            return

        asyncio.run(enricher.enrich(show_progress=True))
        # 重新加载补全后的记录并导出全字段结果
        records = utils.sort_by_subdomain(enricher.load(table))
        output = get_default_output(domain, 'enrich', format)
        if format == 'txt':
            export_subdomains([r['subdomain'] for r in records], output, 'txt')
        else:
            export_results(records, output, format)
        console.print(f"[green]补全结果已保存到: {output}[/green]")
    finally:
        enricher.close()


@app.command("main")
def main(
    target: Optional[str] = typer.Argument(None, help="目标域名（与 -i 二选一）"),
    input_file: Optional[Path] = typer.Option(None, "--input", "-i", help="目标文件（每行一个域名或 URL，批量收集）"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径（批量模式下忽略，按域名各自输出）"),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式: csv/json/txt"),
    brute: bool = typer.Option(True, "--brute/--no-brute", help="启用爆破模块"),
    disable_search: bool = typer.Option(False, "--no-search", help="禁用搜索引擎模块"),
    disable_cert: bool = typer.Option(False, "--no-cert", help="禁用证书查询模块"),
    disable_dataset: bool = typer.Option(False, "--no-dataset", help="禁用数据集模块"),
    altdns: bool = typer.Option(True, "--altdns/--no-altdns", help="启用子域置换模块"),
    save_db: bool = typer.Option(False, "--save-db", help="将各模块结果写入 SQLite（供 enrich 命令使用）"),
    enrich: bool = typer.Option(False, "--enrich", help="收集后自动补全 DNS/HTTP/CDN/IP 信息，额外输出 enrich_域名.csv（自动启用 --save-db）"),
    enrich_concurrent: int = typer.Option(100, "--enrich-concurrent", help="enrich 补全并发数（默认 100）"),
    no_wildcard: bool = typer.Option(False, "--no-wildcard", help="禁用泛解析检测与过滤"),
    wildcard_cidr: bool = typer.Option(False, "--wildcard-cidr", help="启用同 /24 网段泛解析匹配"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """
    收集目标域名的子域名

    示例:
        python justone.py example.com
        python justone.py example.com -o results.csv
        python justone.py example.com --no-brute
        python justone.py example.com --enrich
        python justone.py -i targets.txt
    """
    init_logging(debug=verbose)

    # 解析目标：-i 文件（批量）或单个域名
    domains: list = []
    if input_file:
        if not input_file.exists():
            console.print(f"[bold red]错误: 文件不存在: {input_file}[/bold red]")
            raise typer.Exit(1)
        try:
            domains = utils.read_target_file(str(input_file))
        except OSError as e:
            console.print(f"[bold red]错误: 读取目标文件失败: {e}[/bold red]")
            raise typer.Exit(1)
        if not domains:
            console.print("[bold red]错误: 目标文件中没有有效的域名[/bold red]")
            raise typer.Exit(1)
        console.print(f"[bold cyan]从文件加载 {len(domains)} 个目标域名[/bold cyan]")
    elif target:
        main_domain = Domain(target).registered()
        if not main_domain:
            console.print(f"[bold red]错误:[/bold red] 无法解析目标域名: {target}")
            raise typer.Exit(1)
        if main_domain != target:
            console.print(f"[dim]注册域名: {main_domain}[/dim]")
        domains = [main_domain]
    else:
        console.print("[bold red]错误: 请指定目标域名或使用 -i 指定目标文件[/bold red]")
        raise typer.Exit(1)

    config = {
        'enable_search': not disable_search,
        'enable_certificate': not disable_cert,
        'enable_dataset': not disable_dataset,
        'save_module_result': False,
        'save_db': save_db or enrich,
        'proxy_enable': settings.proxy_enable,
        'LEAKIX_API': settings.leakix_api,
        'wildcard_filter': not no_wildcard,
        'wildcard_probes': settings.wildcard_probes,
        'wildcard_cidr': wildcard_cidr,
    }

    wildcard_config = {
        'wildcard_check': not no_wildcard,
        'wildcard_deal': not no_wildcard,
        'wildcard_probes': settings.wildcard_probes,
        'wildcard_cidr': wildcard_cidr,
    }

    batch = len(domains) > 1
    if batch and output:
        console.print("[dim]批量模式: 忽略 -o，按域名各自输出 collect_<域名>.<格式>[/dim]")

    for index, main_domain in enumerate(domains, 1):
        if batch:
            console.rule(f"[cyan][{index}/{len(domains)}] {main_domain}")
        run_collect_pipeline(
            main_domain, config, wildcard_config,
            brute=brute, altdns=altdns,
            disable_search=disable_search, disable_cert=disable_cert,
            disable_dataset=disable_dataset,
            output=None if batch else output,
            format=format,
            enrich=enrich, enrich_concurrent=enrich_concurrent,
        )


@app.command()
def check(
    target: Optional[str] = typer.Argument(None, help="目标域名"),
    dns_only: bool = typer.Option(False, "--dns", help="仅执行 DNS 检查"),
    dns_security: bool = typer.Option(False, "--dns-security", "--dnssec", help="执行 DNS 安全检测（DNSSEC/投毒/劫持）"),
    cdn_check: bool = typer.Option(False, "--cdn", help="执行 CDN 识别"),
    input_file: Optional[Path] = typer.Option(None, "--input", "-i", help="子域名列表文件（每行一个子域名，支持 CSV/TXT）"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径"),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式: csv/json/txt"),
    dns_concurrent: int = typer.Option(200, "--dns-concurrent", "-dc", help="DNS 解析并发数（默认 200）"),
    cdn_concurrent: int = typer.Option(100, "--cdn-concurrent", "-cc", help="CDN 识别并发数（默认 100）"),
    http_concurrent: int = typer.Option(100, "--http-concurrent", "-hc", help="HTTP 检查并发数（默认 100）"),
    save_db: bool = typer.Option(False, "--save-db", help="将模块发现结果写入 SQLite（供 enrich 命令使用）"),
    no_wildcard: bool = typer.Option(False, "--no-wildcard", help="禁用泛解析检测与过滤"),
    wildcard_cidr: bool = typer.Option(False, "--wildcard-cidr", help="启用同 /24 网段泛解析匹配"),
):
    """
    检查子域名存活状态

    默认先做泛解析检测，将解析到泛解析 IP/CNAME 的子域名全部排除，
    再执行存活检查，避免泛解析造成的大量假阳性。

    示例:
        python justone.py check example.com                    # 检查一个域名
        python justone.py check example.com --dns              # 仅 DNS 检查
        python justone.py check example.com --dns-security     # DNS 安全检测
        python justone.py check -i subdomains.txt -o results   # 从文件批量检查
        python justone.py check example.com --no-wildcard      # 关闭泛解析排除
    """
    from modules.check import DNSCheck
    from modules.check.http import AsyncHTTPCheck
    from modules.check import CertInfo, Robots, Sitemap, CrossDomain, AXFR, NSEC
    from modules.check.cdn import CDNCheck
    from modules.check import DNSSecurityCheck
    from modules.export import export_results

    init_logging()

    subdomains = set()

    if input_file:
        if not input_file.exists():
            console.print(f"[bold red]错误: 文件不存在: {input_file}[/bold red]")
            raise typer.Exit(1)
        subdomains = load_subdomain_file(input_file)

        main_domain = None
        # -i 模式：从第一个子域名提取注册域名，供 DNSSEC/CDN 检测使用
        if subdomains:
            first = next(iter(subdomains))
            extracted = Domain(first).registered()
            if extracted:
                main_domain = extracted
        console.print(f"[bold cyan]从文件加载 {len(subdomains)} 个子域名[/bold cyan]")
    elif target:
        domain_obj = Domain(target)
        main_domain = domain_obj.registered()
        console.print(f"[bold cyan]检查子域名: {main_domain}[/bold cyan]")

        discovery_config = {'save_db': save_db}
        discovery_modules = [
            (CertInfo(main_domain, discovery_config), 'SSL证书'),
            (Robots(main_domain, discovery_config), 'robots.txt'),
            (Sitemap(main_domain, discovery_config), 'sitemap'),
            (CrossDomain(main_domain, discovery_config), 'crossdomain.xml'),
            (AXFR(main_domain, discovery_config), 'DNS域传送'),
            (NSEC(main_domain, discovery_config), 'DNSSEC'),
        ]
        console.print("[cyan]执行域名级检查发现子域名...[/cyan]")
        for mod, label in discovery_modules:
            try:
                result = mod.run()
                if result:
                    subdomains.update(result)
                    console.print(f"  [dim]{label}: 发现 {len(result)} 个[/dim]")
            except Exception as e:
                console.print(f"  [dim]{label}: 跳过 ({e})[/dim]")
        if subdomains:
            console.print(f"[cyan]共发现 {len(subdomains)} 个候选子域名[/cyan]")
    else:
        console.print("[bold red]错误: 请指定目标域名或使用 -i 指定输入文件[/bold red]")
        raise typer.Exit(1)

    # 泛解析过滤：排除解析到泛解析 IP/CNAME 的子域名（避免存活检查假阳性）
    if not no_wildcard and main_domain and subdomains:
        from common.wildcard import detect_and_filter
        console.print("[cyan]检测泛解析...[/cyan]")
        kept, removed, wc_info = detect_and_filter(
            subdomains,
            main_domain,
            probes=settings.wildcard_probes,
            concurrent=min(dns_concurrent, 100),
            include_cidr=wildcard_cidr,
        )
        if wc_info.detected:
            targets = ', '.join(sorted(wc_info.ips)) or ', '.join(sorted(wc_info.cnames)) or 'unknown'
            console.print(
                f"[yellow]检测到泛解析[/yellow]（{targets}），"
                f"已排除 [red]{len(removed)}[/red] 个泛解析域名，剩余 {len(kept)} 个"
            )
            subdomains = kept
        else:
            console.print("[dim]未检测到泛解析[/dim]")

    if dns_only:
        checker = DNSCheck(main_domain or "unknown", concurrent=dns_concurrent)
        results = checker.run(subdomains, show_progress=True)
    else:
        checker = AsyncHTTPCheck(main_domain or "unknown", concurrent=http_concurrent)
        results = checker.run(subdomains, show_progress=True)
    console.print(f"发现 {len(results)} 个存活的子域名")

    if cdn_check and results:
        alive_subdomains = {r['subdomain'] for r in results}
        console.print("[cyan]执行 CDN 识别...[/cyan]")
        cdn = CDNCheck(main_domain or "unknown", concurrent=cdn_concurrent)
        cdn_results = cdn.run(alive_subdomains)
        cdn_count = sum(1 for r in cdn_results if r['cdn'])
        console.print(f"[cyan]CDN 识别完成: {cdn_count}/{len(cdn_results)} 使用 CDN[/cyan]")
        for r in cdn_results:
            if r['cdn']:
                console.print(f"  [dim]{r['subdomain']}: CDN ({r.get('cdn_provider', 'unknown')})[/dim]")

    if dns_security and main_domain:
        console.print(f"\n[bold cyan]DNS 安全检测: {main_domain}[/bold cyan]")
        security = DNSSecurityCheck(main_domain)
        security_results = security.run()
        for r in security_results:
            color = {
                'secure': 'green',
                'insecure': 'yellow',
                'suspicious': 'red',
                'error': 'red',
                'info': 'dim',
            }.get(r.status, 'white')
            console.print(f"  [{color}][{r.status.upper()}][/] {r.check}: {r.detail}")

    if results:
        if not output:
            if input_file and subdomains:
                # -i 模式：从第一个子域名提取注册域名作为文件名
                first = next(iter(subdomains))
                domain_obj = Domain(first)
                extracted = domain_obj.registered()
                if extracted:
                    output = get_default_output(extracted, 'check', format)
                else:
                    output = get_default_output('result', 'check', format)
            else:
                output = get_default_output('result', 'check', format)
        if format == 'txt':
            output.parent.mkdir(parents=True, exist_ok=True)
            with open(output, 'w', encoding='utf-8') as f:
                for r in sorted(results, key=lambda x: x['subdomain']):
                    f.write(f"{r['subdomain']} {r['status']}\n")
        else:
            export_results(results, output, format)
        console.print(f"[green]结果已保存到: {output}[/green]")


@app.command()
def brute(
    target: str = typer.Argument(..., help="目标域名"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径"),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式: csv/json/txt"),
    wordlist: Optional[Path] = typer.Option(None, "--wordlist", "-w", help="爆破字典路径"),
    concurrent: int = typer.Option(2000, "--concurrent", "-c", help="并发数"),
    auth_ns: bool = typer.Option(False, "--auth-ns", help="使用目标域名权威 NS 解析（更快，NS 查询失败自动回退公共 NS 池）"),
    no_wildcard: bool = typer.Option(False, "--no-wildcard", help="禁用泛解析检测与过滤"),
    wildcard_cidr: bool = typer.Option(False, "--wildcard-cidr", help="启用同 /24 网段泛解析匹配"),
):
    """
    仅执行爆破模块

    示例:
        python justone.py brute example.com
        python justone.py brute example.com -w wordlist.txt -c 1000
        python justone.py brute example.com --auth-ns
    """
    init_logging()

    domain_obj = Domain(target)
    main_domain = domain_obj.registered()

    console.print(f"[bold cyan]爆破子域名: {main_domain}[/bold cyan]")

    config = {
        'concurrent': concurrent,
        'wordlist': str(wordlist) if wordlist else None,
        'authoritative_ns': auth_ns,
        'wildcard_check': not no_wildcard,
        'wildcard_deal': not no_wildcard,
        'wildcard_probes': settings.wildcard_probes,
        'wildcard_cidr': wildcard_cidr,
    }

    brute_module = Brute(main_domain, config)
    subdomains = brute_module.run()

    console.print(f"[green]发现 {len(subdomains)} 个子域名，耗时 {brute_module.get_elapse():.1f} 秒[/green]")

    if subdomains:
        if not output:
            output = get_default_output(main_domain, 'brute', format)
        if format == 'txt':
            export_subdomains(sorted(subdomains), output, 'txt')
        else:
            results = [{'subdomain': s} for s in sorted(subdomains)]
            export_results(results, output, format)
        console.print(f"[green]结果已保存到: {output}[/green]")


@app.command()
def altdns(
    target: str = typer.Argument(..., help="目标域名"),
    input_file: Optional[Path] = typer.Option(None, "--input", "-i", help="已知子域名列表文件（每行一个子域名）"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径"),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式: csv/json/txt"),
    concurrent: int = typer.Option(50, "--concurrent", "-c", help="并发数"),
    wordlist: Optional[Path] = typer.Option(None, "--wordlist", "-w", help="置换词表路径"),
    no_prefix: bool = typer.Option(False, "--no-prefix", help="禁用前缀置换"),
    no_suffix: bool = typer.Option(False, "--no-suffix", help="禁用后缀置换"),
    no_number: bool = typer.Option(False, "--no-number", help="禁用数字追加置换"),
    no_insert: bool = typer.Option(False, "--no-insert", help="禁用连字符插入置换"),
    no_wildcard: bool = typer.Option(False, "--no-wildcard", help="禁用泛解析检测与过滤"),
    wildcard_cidr: bool = typer.Option(False, "--wildcard-cidr", help="启用同 /24 网段泛解析匹配"),
):
    """
    对已有子域名进行置换扩展

    基于已知子域名，通过加前缀/后缀/数字/连字符等规则生成新候选并验证。

    示例:
        python justone.py altdns example.com
        python justone.py altdns example.com -i subdomains.txt
        python justone.py altdns example.com -i subdomains.txt --no-number
    """
    init_logging()

    subdomains: Set[str] = set()
    main_domain = Domain(target).registered()

    wildcard_config = {
        'wildcard_check': not no_wildcard,
        'wildcard_deal': not no_wildcard,
        'wildcard_probes': settings.wildcard_probes,
        'wildcard_cidr': wildcard_cidr,
    }

    if input_file:
        if not input_file.exists():
            console.print(f"[bold red]错误: 文件不存在: {input_file}[/bold red]")
            raise typer.Exit(1)
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    subdomains.add(line)
        console.print(f"[bold cyan]从文件加载 {len(subdomains)} 个子域名[/bold cyan]")
        if not main_domain and subdomains:
            first = next(iter(subdomains))
            main_domain = Domain(first).registered()
            console.print(f"[dim]自动推断注册域名: {main_domain}[/dim]")

    if not main_domain:
        console.print(f"[bold red]错误: 无法解析目标域名: {target}[/bold red]")
        raise typer.Exit(1)

    if not input_file:
        console.print(f"[bold cyan]注册域名: {main_domain}[/bold cyan]")

        console.print("[cyan]执行信息收集...[/cyan]")
        collect = Collect(main_domain, {
            'enable_search': True,
            'enable_certificate': True,
            'enable_dataset': True,
            'wildcard_filter': not no_wildcard,
            'wildcard_probes': settings.wildcard_probes,
            'wildcard_cidr': wildcard_cidr,
        })
        subdomains = set(collect.run())
        console.print(f"[dim]收集到 {len(subdomains)} 个子域名[/dim]")

        console.print("[cyan]执行爆破...[/cyan]")
        brute_module = Brute(main_domain, wildcard_config)
        brute_subdomains = brute_module.run()
        subdomains.update(brute_subdomains)
        console.print(f"[dim]爆破发现 {len(brute_subdomains)} 个，共 {len(subdomains)} 个已知子域名[/dim]")

    if not subdomains:
        console.print("[yellow]没有已知子域名，无法执行置换[/yellow]")
        return

    config = {
        'concurrent': concurrent,
        'prefix': not no_prefix,
        'suffix': not no_suffix,
        'number': not no_number,
        'insert': not no_insert,
    }
    config.update(wildcard_config)
    if wordlist:
        config['wordlist'] = str(wordlist)

    console.print(f"[cyan]开始子域置换（已知 {len(subdomains)} 个）...[/cyan]")
    altdns_module = Altdns(main_domain, subdomains, config)
    altdns_subdomains = altdns_module.run(show_progress=True)

    console.print(f"[green]置换完成: 发现 {len(altdns_subdomains)} 个新子域名，耗时 {altdns_module.get_elapse():.1f} 秒[/green]")

    if altdns_subdomains:
        if not output:
            output = get_default_output(target, 'altdns', format)
        if format == 'txt':
            export_subdomains(sorted(altdns_subdomains), output, 'txt')
        else:
            results = [{'subdomain': s} for s in sorted(altdns_subdomains)]
            export_results(results, output, format)
        console.print(f"[green]结果已保存到: {output}[/green]")


@app.command()
def takeover(
    target: Optional[str] = typer.Argument(None, help="目标域名"),
    input_file: Optional[Path] = typer.Option(None, "--input", "-i", help="子域名列表文件（每行一个子域名）"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径"),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式: csv/json/txt"),
    concurrent: int = typer.Option(20, "--concurrent", "-c", help="并发数"),
    fingerprint_file: Optional[Path] = typer.Option(None, "--fingerprint-file", help="自定义接管指纹文件路径"),
    skip_brute: bool = typer.Option(False, "--skip-brute", help="跳过爆破阶段（仅从收集模块获取子域名）"),
    no_pre_check: bool = typer.Option(False, "--no-pre-check", help="跳过存活预检（直接对所有子域名做 CNAME 接管检测）"),
    no_progress: bool = typer.Option(False, "--no-progress", help="隐藏进度条"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """
    检测子域名接管风险

    通过 DNS CNAME + HTTP 响应指纹双重确认判断子域名是否可被接管。

    示例:

        python justone.py takeover example.com

        python justone.py takeover -i subdomains.txt

        python justone.py takeover example.com --concurrent 50
    """
    init_logging(debug=verbose)

    subdomains: Set[str] = set()
    main_domain: Optional[str] = None

    if input_file:
        if not input_file.exists():
            console.print(f"[bold red]错误: 文件不存在: {input_file}[/bold red]")
            raise typer.Exit(1)
        subdomains = load_subdomain_file(input_file)
        console.print(f"[bold cyan]从文件加载 {len(subdomains)} 个子域名[/bold cyan]")
    elif target:
        domain_obj = Domain(target)
        main_domain = domain_obj.registered()
        if not main_domain:
            console.print(f"[bold red]错误: 无法解析目标域名: {target}[/bold red]")
            raise typer.Exit(1)
        console.print(f"[bold cyan]检测子域名接管: {main_domain}[/bold cyan]")

        # 先收集子域名
        console.print("[cyan]执行信息收集...[/cyan]")
        collect = Collect(main_domain)
        collected = set(collect.run())
        console.print(f"[dim]收集到 {len(collected)} 个子域名[/dim]")

        # 再加爆破（除非跳过）
        if not skip_brute:
            console.print("[cyan]执行爆破...[/cyan]")
            brute_module = Brute(main_domain)
            brute_subdomains = brute_module.run()
            console.print(f"[dim]爆破发现 {len(brute_subdomains)} 个[/dim]")
            subdomains = collected | brute_subdomains
        else:
            subdomains = collected
    else:
        console.print("[bold red]错误: 请指定目标域名或使用 -i 指定输入文件[/bold red]")
        raise typer.Exit(1)

    if not subdomains:
        console.print("[yellow]没有子域名需要检测[/yellow]")
        return

    console.print(f"[cyan]开始检测 {len(subdomains)} 个子域名的接管风险...[/cyan]")

    config = {
        'concurrent': concurrent,
        'show_progress': not no_progress,
        'pre_check': not no_pre_check,
    }
    if fingerprint_file:
        config['fingerprint_file'] = str(fingerprint_file)

    results = takeover_run(main_domain or 'target', subdomains, config)

    # 统计
    vulnerable = [r for r in results if r['status'] == 'vulnerable']
    likely = [r for r in results if r['status'] == 'likely']
    errors = [r for r in results if r['status'] == 'error']
    dead = [r for r in results if r.get('detail', {}).get('pre_check') == 'dead']
    safe = len(results) - len(vulnerable) - len(likely) - len(errors) - len(dead)

    console.print("\n[bold]检测完成:[/bold]")
    if dead:
        console.print(f"  [dim]存活预检: {len(subdomains)} → {len(subdomains) - len(dead)} 存活, {len(dead)} 已死（跳过接管检测）[/dim]")
    console.print(f"  [bold red]可接管: {len(vulnerable)}[/bold red]")
    console.print(f"  [bold yellow]可疑: {len(likely)}[/bold yellow]")
    console.print(f"  [dim]安全: {safe}[/dim]")
    console.print(f"  [dim]错误: {len(errors)}[/dim]")

    if vulnerable:
        console.print("\n[bold red]!!! 可接管域名 !!![/bold red]")
        for r in vulnerable:
            console.print(f"  [red]{r['subdomain']}[/red] → {r['cname']} ({r['service']})")

    if likely:
        console.print("\n[bold yellow]可疑域名:[/bold yellow]")
        for r in likely:
            console.print(f"  [yellow]{r['subdomain']}[/yellow] → {r['cname']} ({r['service']})")

    if results:
        if not output:
            if main_domain:
                output = get_default_output(main_domain, 'takeover', format)
            else:
                output = get_default_output('result', 'takeover', format)
        if format == 'txt':
            export_subdomains(
                [f"{r['subdomain']}|{r['status']}|{r.get('service', '')}|{r.get('cname', '')}"
                 for r in results],
                output, 'txt'
            )
        else:
            export_results(results, output, format)
        console.print(f"[green]结果已保存到: {output}[/green]")


@app.command()
def enrich(
    db_path: str = typer.Argument(..., help="SQLite 数据库文件路径（如 results/result.sqlite3）"),
    table_name: Optional[str] = typer.Option(None, "--table", "-t", help="指定表名（不指定则自动检测）"),
    concurrent: int = typer.Option(100, "--concurrent", "-c", help="HTTP 检查并发数"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """
    丰富已有子域名信息

    从 SQLite 数据库读取已有子域名记录，通过 DNS 解析、HTTP 探测、
    CDN 识别、IP 定位等方式补全缺失信息并更新数据库。

    示例:

        python justone.py enrich results/result.sqlite3

        python justone.py enrich results/result.sqlite3 -c 200

        python justone.py enrich results/result.sqlite3 -t example_com
    """
    init_logging(debug=verbose)

    db_file = Path(db_path)
    if not db_file.exists():
        console.print(f"[bold red]错误: 数据库文件不存在: {db_file}[/bold red]")
        raise typer.Exit(1)

    console.print(f"[bold green]JustOne[/bold green] 开始丰富子域名信息: [cyan]{db_file}[/cyan]")

    enricher = Enrich(str(db_file), concurrent=concurrent)
    try:
        enricher.load(table_name)
        if not enricher.records:
            console.print("[yellow]数据库中没有记录需要丰富[/yellow]")
            return

        console.print(f"[cyan]共 {len(enricher.records)} 条记录，开始丰富...[/cyan]")
        updated = asyncio.run(enricher.enrich(show_progress=True))
        console.print(f"[bold green]完成![/bold green] 更新了 [yellow]{updated}[/yellow] 条记录")
    finally:
        enricher.close()


if __name__ == "__main__":
    app()