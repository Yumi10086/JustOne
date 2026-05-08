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
        "<cyan>{name}:{line}</cyan> "
        "<level>{message}</level>"
    )

    logger.add(sys.stderr, level=level, format=fmt)
    logger.add(
        log_path,
        level="DEBUG",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <5} | {name}.{function}:{line} | {message}",
        rotation="10 MB",
        retention="7 days"
    )

    return logger