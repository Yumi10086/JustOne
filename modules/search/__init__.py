"""
搜索引擎模块
"""

from .baidu import BaiduSearch, run as baidu_run
from .bing import BingSearch, run as bing_run

__all__ = ['BaiduSearch', 'BingSearch', 'baidu_run', 'bing_run']