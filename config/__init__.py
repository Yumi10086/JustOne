"""JustOne 配置模块"""

from config.settings import Settings, settings
from config.logging import init_logging

__all__ = ['Settings', 'settings', 'init_logging']