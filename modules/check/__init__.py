"""
子域验证模块
"""

from .http import HTTPCheck
from .dns import DNSCheck

__all__ = ['HTTPCheck', 'DNSCheck']