#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JustOne - 子域名收集工具
=========================

一、基本收集
    python justone.py main example.com                    # 完整收集（搜索+证书+数据集+爆破）
    python justone.py main example.com --no-brute        # 禁用爆破模块
    python justone.py main example.com --no-search       # 禁用搜索引擎模块
    python justone.py main example.com --no-cert         # 禁用证书查询模块
    python justone.py main example.com --no-dataset      # 禁用数据集查询模块

二、仅执行爆破
    python justone.py brute example.com                   # 使用默认字典爆破
    python justone.py brute example.com -c 1000          # 设置并发数
    python justone.py brute example.com -w wordlist.txt  # 指定字典文件

三、检查存活状态
    python justone.py check example.com                  # HTTP 存活检查
    python justone.py check example.com --dns            # 仅 DNS 检查
    python justone.py check -i subdomains.txt             # 从文件批量检查
    python justone.py check -i subdomains.txt -f txt     # 指定输出格式

四、输出选项
    -o, --output PATH      指定输出文件路径（默认: results/目录）
    -f, --format FORMAT   输出格式: csv/json/txt（默认: csv）

    # 默认输出到 results/ 目录，自动添加功能前缀:
    #   main 命令   -> results/collect_域名.csv
    #   brute 命令  -> results/brute_域名.csv
    #   check 命令  -> results/check_域名.csv

五、其他
    python justone.py --version                          # 查看版本
    python justone.py --help                             # 查看帮助
    python justone.py main --help                        # 查看 main 命令帮助
"""

import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from config.logging import init_logging
from config.settings import settings
from modules.collect import Collect
from modules.brute import Brute
from modules.export import export_subdomains, export_results
from common.domain import Domain
from common import utils

# 初始化全局 HTTP 配置（代理等）
utils.set_http_config(
    timeout=settings.http_timeout,
    verify_ssl=settings.http_verify_ssl,
    enable_random_ua=settings.http_enable_random_ua,
    proxy_enable=settings.proxy_enable,
    proxy_pool=settings.get_proxy_list(),
)


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


@app.command("main")
def main(
    target: str = typer.Argument(..., help="目标域名"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径"),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式: csv/json/txt"),
    brute: bool = typer.Option(True, "--brute/--no-brute", help="启用爆破模块"),
    disable_search: bool = typer.Option(False, "--no-search", help="禁用搜索引擎模块"),
    disable_cert: bool = typer.Option(False, "--no-cert", help="禁用证书查询模块"),
    disable_dataset: bool = typer.Option(False, "--no-dataset", help="禁用数据集模块"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """
    收集目标域名的子域名

    示例:
        python justone.py example.com
        python justone.py example.com -o results.csv
        python justone.py example.com --no-brute
    """
    init_logging(debug=verbose)

    console.print(f"[bold green]JustOne[/bold green] 开始收集子域名: [cyan]{target}[/cyan]")

    domain_obj = Domain(target)
    main_domain = domain_obj.registered()

    if not main_domain:
        console.print(f"[bold red]错误:[/bold red] 无法解析目标域名: {target}")
        raise typer.Exit(1)

    if main_domain != target:
        console.print(f"[dim]注册域名: {main_domain}[/dim]")

    config = {
        'enable_search': not disable_search,
        'enable_certificate': not disable_cert,
        'enable_dataset': not disable_dataset,
        'save_module_result': False,
        'proxy_enable': settings.proxy_enable,
        'LEAKIX_API': settings.leakix_api,
    }

    subdomains = set()
    total_elapse = 0

    import sys

    def show_progress(description: str, start_time: float):
        """单行进度显示"""
        elapsed = time.time() - start_time
        sys.stdout.write(f'\r  {description} [{elapsed:.1f}s]')
        sys.stdout.flush()

    if not (disable_search and disable_cert and disable_dataset):
        start = time.time()
        sys.stdout.write('  执行信息收集模块... ')
        sys.stdout.flush()
        collect = Collect(main_domain, config)
        subdomains = set(collect.run())
        total_elapse += collect.elapse or 0
        show_progress('完成', start)
        print()

    if brute:
        start = time.time()
        sys.stdout.write('  执行爆破模块... ')
        sys.stdout.flush()
        brute_module = Brute(main_domain)
        brute_subdomains = brute_module.run()
        subdomains.update(brute_subdomains)
        total_elapse += brute_module.get_elapse() or 0
        show_progress('完成', start)
        print()

    if subdomains:
        console.print(f"\n[bold green]完成![/bold green] 共发现 [yellow]{len(subdomains)}[/yellow] 个子域名")
        console.print(f"[dim]总耗时: {total_elapse:.1f} 秒[/dim]")

        if not output:
            output = get_default_output(main_domain, 'collect', format)
        if format == 'txt':
            export_subdomains(sorted(subdomains), output, 'txt')
        else:
            results = [{'subdomain': s} for s in sorted(subdomains)]
            export_results(results, output, format)
        console.print(f"[green]结果已保存到: {output}[/green]")
    else:
        console.print(f"\n[yellow]未发现子域名[/yellow]")


@app.command()
def check(
    target: Optional[str] = typer.Argument(None, help="目标域名"),
    dns_only: bool = typer.Option(False, "--dns", help="仅执行 DNS 检查"),
    input_file: Optional[Path] = typer.Option(None, "--input", "-i", help="子域名列表文件（每行一个子域名）"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径"),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式: csv/json/txt"),
):
    """
    检查子域名存活状态

    示例:
        python justone.py check example.com                    # 检查一个域名
        python justone.py check example.com --dns              # 仅 DNS 检查
        python justone.py check -i subdomains.txt -o results   # 从文件批量检查
    """
    from modules.check import DNSCheck, HTTPCheck
    from modules.check.http import AsyncHTTPCheck
    from modules.export import export_results, export_subdomains

    init_logging()

    subdomains = set()

    if input_file:
        if not input_file.exists():
            console.print(f"[bold red]错误: 文件不存在: {input_file}[/bold red]")
            raise typer.Exit(1)
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    subdomains.add(line)
        main_domain = None
        console.print(f"[bold cyan]从文件加载 {len(subdomains)} 个子域名[/bold cyan]")
    elif target:
        domain_obj = Domain(target)
        main_domain = domain_obj.registered()
        console.print(f"[bold cyan]检查子域名: {main_domain}[/bold cyan]")
    else:
        console.print("[bold red]错误: 请指定目标域名或使用 -i 指定输入文件[/bold red]")
        raise typer.Exit(1)

    if dns_only:
        checker = DNSCheck(main_domain or "unknown")
    else:
        checker = AsyncHTTPCheck(main_domain or "unknown", concurrent=100)

    results = checker.run(subdomains, show_progress=True)
    console.print(f"发现 {len(results)} 个存活的子域名")

    if results:
        if not output:
            if main_domain and main_domain != 'unknown':
                output = get_default_output(main_domain, 'check', format)
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
):
    """
    仅执行爆破模块

    示例:
        python justone.py brute example.com
        python justone.py brute example.com -w wordlist.txt -c 1000
    """
    init_logging()

    domain_obj = Domain(target)
    main_domain = domain_obj.registered()

    console.print(f"[bold cyan]爆破子域名: {main_domain}[/bold cyan]")

    config = {
        'concurrent': concurrent,
        'wordlist': str(wordlist) if wordlist else None,
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


if __name__ == "__main__":
    app()