"""
JustOne 配置文件
基于 Pydantic BaseSettings，读取环境变量
"""

import os
from pathlib import Path
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


def get_auto_thread_count() -> int:
    """根据 CPU 核心数自动计算线程数"""
    cpu_count = os.cpu_count() or 4
    return cpu_count * 2


def parse_bool(value) -> bool:
    """解析布尔值，支持多种格式"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


# ==================== 主配置类 ====================

class Settings(BaseSettings):
    """
    JustOne 主配置类
    基于 pydantic_settings.BaseSettings，支持从 .env 文件读取配置
    """

    # ==================== 路径配置（自动计算）====================
    # 项目根目录
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    # 数据存放目录
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data")
    # 结果保存目录
    results_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "results")
    # 临时文件目录
    temp_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "results" / "temp")

    # ==================== 通用配置 ====================
    # 开启版本检查
    enable_check_version: bool = True
    # 结果保存格式，可选 "csv" 或 "json"
    result_save_format: str = "csv"
    # 只导出存活的子域
    result_export_alive: bool = False

    # ==================== HTTP 配置 ====================
    # 请求超时时间（秒）
    http_timeout: int = 15
    # SSL 证书验证（生产环境建议开启）
    http_verify_ssl: bool = False
    # 允许重定向
    http_allow_redirect: bool = True
    # 使用随机 User-Agent
    http_enable_random_ua: bool = True
    # 请求线程数（默认空则自动设置）
    http_thread_count: Optional[int] = None
    # 最大重定向次数
    http_redirect_limit: int = 10

    # ==================== 代理配置 ====================
    # 是否启用代理
    proxy_enable: bool = False

    # ==================== 暴力破解模块配置 ====================
    # 启用暴力破解模块
    brute_enable: bool = True
    # 并发数量（最大推荐 10000）
    brute_concurrent: int = 2000
    # 启用递归爆破
    brute_recursive: bool = False
    # 递归爆破深度
    brute_recursive_depth: int = 2
    # 开启泛解析检测
    brute_wildcard_check: bool = True
    # 开启泛解析处理
    brute_wildcard_deal: bool = True

    # ==================== 信息收集模块配置 ====================
    # 启用信息收集模块
    collect_enable: bool = True
    # 每个收集模块超时时间（秒）
    collect_module_timeout: int = 120
    # 最大并发数
    collect_max_concurrent: int = 50

    # ==================== DNS 解析配置 ====================
    # 启用 DNS 解析（默认使用 223.5.5.5, 119.29.29.29, 114.114.114.114, 8.8.8.8, 1.1.1.1）
    dns_enable: bool = True

    # ==================== 端口探测配置 ====================
    # 启用端口探测
    portscan_enable: bool = True
    # 端口范围模式：small / medium / large
    portscan_mode: str = "small"

    # ==================== 搜索模块配置 ====================
    # 启用搜索模块
    search_enable: bool = True
    # 启用全量搜索（获取全部结果，可能耗时较长）
    search_enable_full_search: bool = False
    # 启用递归搜索
    search_enable_recursive_search: bool = False
    # 递归搜索层数
    search_recursive_times: int = 2

    # ==================== 其他模块配置 ====================
    # 启用证书模块
    certificate_enable: bool = True
    # 启用数据集模块
    datasets_enable: bool = True
    # 启用情报模块
    intelligence_enable: bool = True
    # 启用指纹识别模块
    fingerprint_enable: bool = True
    # 启用子域接管检查
    takeover_enable: bool = False
    # 启用导出模块
    export_enable: bool = True

    # ==================== API 凭证配置 ====================
    # Censys: https://censys.io/api
    censys_api_id: str = ""
    censys_api_secret: str = ""
    # Binaryedge: https://app.binaryedge.io/account/api
    binaryedge_api: str = ""
    # Chinaz: http://api.chinaz.com/ApiDetails/Alexa
    chinaz_api: str = ""
    # Bing: https://azure.microsoft.com/zh-cn/services/cognitive-services/bing-web-search-api/
    bing_api_id: str = ""
    bing_api_key: str = ""
    # SecurityTrails: https://securitytrails.com/corp/api
    securitytrails_api: str = ""
    # FOFA: https://fofa.so/api
    fofa_email: str = ""
    fofa_api_key: str = ""
    # Google: https://developers.google.com/custom-search/v1/overview
    google_api_id: str = ""
    google_api_key: str = ""
    # RiskIQ: https://api.passivedotal.org/api/docs/
    riskiq_username: str = ""
    riskiq_api_key: str = ""
    # Shodan: https://account.shodan.io/register
    shodan_api_key: str = ""
    # ThreatBook: https://x.threatbook.cn/nodev4/vb4/myAPI
    threatbook_api_key: str = ""
    # VirusTotal: https://developers.virustotal.com/reference
    virustotal_api_key: str = ""
    # ZoomEye: https://www.zoomeye.org/doc?channel=api
    zoomeye_email: str = ""
    zoomeye_password: str = ""
    # Spyse: https://spyse.com/
    spyse_api_token: str = ""
    # CIRCL: https://www.circl.lu/services/passive-dns/
    circl_username: str = ""
    circl_password: str = ""
    # DNSDB: https://www.dnsdb.info/
    dnsdb_api_key: str = ""
    # IPv4Info: http://ipv4info.com/tools/api/
    ipv4info_api_key: str = ""
    # PassiveDNS: https://github.com/360netlab/flint
    passivedns_addr: str = ""
    passivedns_token: str = ""
    # GitHub: https://github.com/settings/tokens
    github_api_user: str = ""
    github_token: str = ""
    # Cloudflare: https://dash.cloudflare.com/profile/api-tokens
    cloudflare_api_token: str = ""
    # Hunter: https://hunter.qianxin.com/home/userInfo
    hunter_api_key: str = ""
    # FullHunt: https://api-docs.fullhunt.io/
    fullhunt_api_key: str = ""
    # HackerTarget: https://api.hackertarget.com/
    hackertarget_api_key: str = ""
    # 360 Quake: https://quake.360.cn/
    quake_api_key: str = ""

    @field_validator("http_thread_count", mode="before")
    @classmethod
    def auto_set_thread_count(cls, v: Optional[int]) -> int:
        """自动设置线程数：未配置时根据 CPU 核心数计算"""
        if v is None or v == 0:
            return get_auto_thread_count()
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()