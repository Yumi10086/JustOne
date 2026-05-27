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
    # 代理地址列表，例如 ["http://127.0.0.1:10809", "http://127.0.0.1:7890"]
    proxy_pool: str = ""

    def get_proxy_list(self) -> list:
        """解析代理池字符串为列表"""
        if not self.proxy_pool:
            return []
        return [addr.strip() for addr in self.proxy_pool.split(",") if addr.strip()]

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
    # 子域名接管检测并发数
    takeover_concurrent: int = 20
    # 启用导出模块
    export_enable: bool = True

    # ==================== API 凭证配置 ====================
    # Censys: https://censys.io/api
    censys_api_id: str = ""
    censys_api_secret: str = ""
    censys_api_token: str = ""
    # Chinaz: http://api.chinaz.com/ApiDetails/Alexa
    chinaz_api: str = ""
    # SecurityTrails: https://securitytrails.com/corp/api
    securitytrails_api: str = ""
    # FOFA: https://fofa.so/api
    fofa_email: str = ""
    fofa_api_key: str = ""
    # Shodan: https://account.shodan.io/register
    shodan_api_key: str = ""
    # ZoomEye: https://www.zoomeye.org/doc?channel=api
    zoomeye_api: str = ""
    # CIRCL: https://www.circl.lu/services/passive-dns/
    circl_username: str = ""
    circl_password: str = ""
    # GitHub: https://github.com/settings/tokens
    github_api_user: str = ""
    github_token: str = ""
    # Cloudflare: https://dash.cloudflare.com/profile/api-tokens
    cloudflare_api_token: str = ""
    # Hunter: https://hunter.qianxin.com/home/userInfo
    hunter_api_key: str = ""
    # FullHunt: https://api-docs.fullhunt.io/
    fullhunt_api_key: str = ""
    # DNSDumpster: https://dnsdumpster.com/developer/
    dnsdumpster_api_key: str = ""
    # LeakIX: https://leakix.net/settings/api
    leakix_api: str = ""
    # AlienVault OTX: https://otx.alienvault.com/settings/api
    alienvault_api_key: str = ""
    # URLScan: https://urlscan.io/user/profile/
    urlscan_api_key: str = ""
    # ThreatBook (微步在线): https://x.threatbook.com/v5/myApi
    threatbook_api_key: str = ""
    # VirusTotal: https://www.virustotal.com/gui/my-apikey
    virustotal_api_key: str = ""
    # VirusTotal 分页每页间隔秒数（免费版 4 req/min，建议 ≥15；付费 API 可降至 1-2）
    virustotal_page_delay: int = 16
    # VirusTotal 最大拉取页数（每页 40 条，50 页 = 2000 条）
    virustotal_max_pages: int = 50


    @field_validator("http_thread_count", mode="before")
    @classmethod
    def parse_empty_thread_count(cls, v):
        """处理空字符串为 None"""
        if v == '' or v is None:
            return None
        return v

    @field_validator("http_thread_count", mode="before")
    @classmethod
    def auto_set_thread_count(cls, v: Optional[int]) -> int:
        """自动设置线程数：未配置时根据 CPU 核心数计算"""
        if v is None or v == 0:
            return get_auto_thread_count()
        return v

    class Config:
        env_file = "config/.env"
        env_file_encoding = "utf-8"


settings = Settings()


class ConfigManager:
    """统一配置管理器 - 提供向后兼容的配置访问"""

    def __init__(self):
        self._settings = settings

    @property
    def http_config(self):
        return {
            'timeout': self._settings.http_timeout,
            'verify_ssl': self._settings.http_verify_ssl,
            'enable_random_ua': self._settings.http_enable_random_ua,
            'proxy_enable': self._settings.proxy_enable,
            'proxy_pool': self._settings.get_proxy_list(),
            'dns_nameservers': ['223.5.5.5', '119.29.29.29'],
            'dns_timeout': 5,
        }

    @property
    def resolve_config(self):
        return {
            'nameservers': ['223.5.5.5', '119.29.29.29', '114.114.114.114', '8.8.8.8', '1.1.1.1'],
            'timeout': 5,
            'lifetime': 10.0,
        }

    @property
    def data_config(self):
        return {
            'data_dir': self._settings.data_dir,
        }

    @property
    def db_config(self):
        return {
            'db_path': self._settings.data_dir / 'justone.db',
        }

    @property
    def ipreg_config(self):
        return {
            'timeout': self._settings.http_timeout,
            'verify_ssl': self._settings.http_verify_ssl,
        }

    @property
    def ip_asn_config(self):
        return {
            'timeout': self._settings.http_timeout,
            'verify_ssl': self._settings.http_verify_ssl,
        }

    @property
    def export_config(self):
        return {
            'format': self._settings.result_save_format,
            'alive_only': self._settings.result_export_alive,
        }

    @property
    def collect_config(self):
        return {
            'enable': self._settings.collect_enable,
            'timeout': self._settings.collect_module_timeout,
            'max_concurrent': self._settings.collect_max_concurrent,
        }

    @property
    def brute_config(self):
        return {
            'enable': self._settings.brute_enable,
            'concurrent': self._settings.brute_concurrent,
            'recursive': self._settings.brute_recursive,
            'recursive_depth': self._settings.brute_recursive_depth,
            'wildcard_check': self._settings.brute_wildcard_check,
            'wildcard_deal': self._settings.brute_wildcard_deal,
        }


config_manager = ConfigManager()