"""
数据集查询模块
"""

from .leakix import LeakIX, run as leakix_run

__all__ = ['LeakIX', 'leakix_run']