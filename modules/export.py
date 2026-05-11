"""
导出模块
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.logging import logger


export_config = {
    'default_format': 'csv',
    'default_output_dir': None,
}


def set_export_config(config: dict):
    """设置导出模块全局配置"""
    export_config.update(config)


def export_results(results: List[Dict[str, Any]], output: Path, format: str = 'csv'):
    """
    导出子域结果到文件

    :param List[Dict[str, Any]] results: 结果列表
    :param Path output: 输出文件路径
    :param str format: 导出格式，支持 'csv' 和 'json'
    """
    if not results:
        logger.warning('结果为空，无需导出')
        return False

    output.parent.mkdir(parents=True, exist_ok=True)

    format = format.lower()
    if format == 'json':
        return _export_json(results, output)
    else:
        return _export_csv(results, output)


def _export_csv(results: List[Dict[str, Any]], output: Path) -> bool:
    """
    导出为 CSV 格式

    :param List[Dict[str, Any]] results: 结果列表
    :param Path output: 输出文件路径
    :return: 是否导出成功
    """
    try:
        headers = results[0].keys()
        with open(output, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results)
        logger.info(f'结果已导出到文件: {output}')
        return True
    except Exception as e:
        logger.error(f'CSV 导出失败: {e}')
        return False


def _export_json(results: List[Dict[str, Any]], output: Path) -> bool:
    """
    导出为 JSON 格式

    :param List[Dict[str, Any]] results: 结果列表
    :param Path output: 输出文件路径
    :return: 是否导出成功
    """
    try:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f'结果已导出到文件: {output}')
        return True
    except Exception as e:
        logger.error(f'JSON 导出失败: {e}')
        return False


def export_subdomains(subdomains: List[str], output: Path, format: str = 'txt'):
    """
    导出子域名列表（简单格式）

    :param List[str] subdomains: 子域名列表
    :param Path output: 输出文件路径
    :param str format: 导出格式，支持 'txt' 和 'json'
    """
    if not subdomains:
        logger.warning('子域名列表为空，无需导出')
        return False

    output.parent.mkdir(parents=True, exist_ok=True)

    format = format.lower()
    if format == 'json':
        try:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(subdomains, f, ensure_ascii=False, indent=2)
            logger.info(f'结果已导出到文件: {output}')
            return True
        except Exception as e:
            logger.error(f'JSON 导出失败: {e}')
            return False
    else:
        try:
            with open(output, 'w', encoding='utf-8') as f:
                for subdomain in subdomains:
                    f.write(subdomain + '\n')
            logger.info(f'结果已导出到文件: {output}')
            return True
        except Exception as e:
            logger.error(f'文本导出失败: {e}')
            return False


def results_to_dict(subdomains: List[str], module: str = 'unknown') -> List[Dict[str, Any]]:
    """
    将子域名列表转换为结果字典

    :param List[str] subdomains: 子域名列表
    :param str module: 来源模块
    :return: 结果字典列表
    """
    results = []
    for subdomain in subdomains:
        results.append({
            'subdomain': subdomain,
            'module': module,
        })
    return results