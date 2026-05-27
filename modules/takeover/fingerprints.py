# -*- coding: utf-8 -*-
"""
指纹加载与匹配模块

提供从 JSON 数据源加载子域名接管指纹、
检查 CNAME 是否匹配指纹模式、以及查找
给定 CNAME 对应的指纹信息等功能。
"""

import json
import re
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / 'data'
_DEFAULT_FINGERPRINT_FILE = _DATA_DIR / 'takeover_fingerprints.json'


def load_fingerprints(path: Optional[Path] = None, reload: bool = False) -> dict:
    """
    加载指纹 JSON 文件，返回 {service_id: fingerprint_data} 字典

    :param path: 指纹文件路径，默认 data/takeover_fingerprints.json
    :param reload: 是否重新加载（当前仅重新读取文件）
    :return: 指纹字典
    :raises FileNotFoundError: 文件不存在时抛出
    :raises json.JSONDecodeError: JSON 解析失败时抛出
    """
    if path is None:
        if _DEFAULT_FINGERPRINT_FILE.exists():
            path = _DEFAULT_FINGERPRINT_FILE
        else:
            path = Path('data/takeover_fingerprints.json')

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def match_cname(cname: str, fingerprint: dict) -> Optional[str]:
    """
    检查 CNAME 目标是否匹配某个指纹的 cname 模式

    支持三种匹配类型（由 fingerprint['cname_match'] 指定）：
      - 'suffix'  : 后缀匹配，使用 str.endswith()
      - 'regex'   : 正则匹配，使用 re.search()
      - 'contains': 子串匹配，使用 in 操作符

    :param cname: CNAME 目标值（小写）
    :param fingerprint: 指纹字典
    :return: 匹配到的模式字符串，无匹配则返回 None
    """
    match_type = fingerprint.get('cname_match', 'suffix')
    patterns = fingerprint.get('cname', [])

    cname_lower = cname.lower()

    for pattern in patterns:
        if match_type == 'suffix':
            if cname_lower.endswith(pattern.lower()):
                return pattern
        elif match_type == 'regex':
            if re.search(pattern, cname_lower, re.IGNORECASE):
                return pattern
        elif match_type == 'contains':
            if pattern.lower() in cname_lower:
                return pattern

    return None


def find_matching_fingerprint(cname: str, fingerprints: dict) -> Optional[tuple]:
    """
    在所有指纹中查找与给定 CNAME 匹配的第一个指纹

    :param cname: CNAME 目标值
    :param fingerprints: 指纹字典 {service_id: fingerprint_data}
    :return: (service_id, fingerprint_dict, matched_pattern) 或 None
    """
    for service_id, fp in fingerprints.items():
        matched = match_cname(cname, fp)
        if matched is not None:
            return (service_id, fp, matched)

    return None
