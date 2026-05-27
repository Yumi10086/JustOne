"""
子域名接管检测模块
"""

from .fingerprints import load_fingerprints, match_cname, find_matching_fingerprint

try:
    from .takeover import TakeoverCheck, TakeoverResult, takeover_run
except ImportError:
    TakeoverCheck = None  # type: ignore
    TakeoverResult = None  # type: ignore
    takeover_run = None  # type: ignore

__all__ = [
    'load_fingerprints', 'match_cname', 'find_matching_fingerprint',
]
