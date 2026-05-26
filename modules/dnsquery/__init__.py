"""
DNS 查询模块
"""

from .mx import MXQuery
from .ns import QueryNS
from .soa import QuerySOA
from .spf import QuerySPF
from .txt import QueryTXT

__all__ = ['MXQuery', 'QueryNS', 'QuerySOA', 'QuerySPF', 'QueryTXT']
