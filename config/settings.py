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