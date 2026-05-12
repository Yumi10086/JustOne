"""
模块接口协议定义

定义各功能模块的标准接口，用于类型检查和模块规范化。
"""

from typing import Protocol, Set, List, Dict, Any, Optional


class BaseModule(Protocol):
    """基础模块协议"""

    @property
    def module(self) -> str:
        """模块名称"""
        ...

    @property
    def source(self) -> str:
        """数据源名称"""
        ...

    @property
    def domain(self) -> str:
        """目标域名"""
        ...

    @property
    def subdomains(self) -> Set[str]:
        """收集到的子域名集合"""
        ...


class CollectModule(BaseModule):
    """收集模块协议 - 用于从各种数据源收集子域名"""

    def run(self) -> Set[str]:
        """
        执行模块收集

        :return: 收集到的子域名集合
        """
        ...

    def begin(self) -> None:
        """记录模块开始"""
        ...

    def finish(self) -> None:
        """记录模块结束"""
        ...


class CheckModule(BaseModule):
    """检查模块协议 - 用于验证子域名存活状态"""

    def run(self, subdomains: Set[str]) -> List[Dict[str, Any]]:
        """
        检查子域名

        :param subdomains: 要检查的子域名集合
        :return: 检查结果列表
        """
        ...


class ExportModule(Protocol):
    """导出模块协议 - 用于导出子域名结果"""

    def export(self, subdomains: Set[str], output_path: str, fmt: str = 'csv') -> bool:
        """
        导出结果

        :param subdomains: 子域名集合
        :param output_path: 输出文件路径
        :param fmt: 导出格式 (csv/json)
        :return: 是否成功
        """
        ...


class BruteModule(Protocol):
    """爆破模块协议 - 用于暴力破解子域名"""

    def run(self, domain: str, wordlist: Optional[str] = None) -> Set[str]:
        """
        执行暴力破解

        :param domain: 目标域名
        :param wordlist: 字典文件路径
        :return: 发现的子域名集合
        """
        ...