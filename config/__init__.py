"""JustOne 配置模块"""

from config.settings import settings, Settings
from config.logging import init_logging

__all__ = ["settings", "Settings", "init_logging"]