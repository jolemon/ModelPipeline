"""
变量分类分析器

提供变量命中分析、歧义检测、来源追溯等功能。
独立于 MetadataManager，专注于"分析"职责。
"""

from typing import List, Dict


class VariableClassifier:
    """
    变量分类分析器

    基于 MetadataManager 的数据，提供变量级别的分析功能：
    - 变量命中检测（found / not_found）
    - 歧义变量检测（同一变量存在于多张表）
    - 变量来源追溯
    """

    def __init__(self, metadata_manager):
        """
        初始化分类分析器

        Args:
            metadata_manager: MetadataManager 实例，提供 variables 和 tables 数据
        """
        self._metadata = metadata_manager

    def classify_variables(self, var_names: List[str]) -> Dict[str, List[str]]:
        """将变量按是否命中元数据进行分类

        Args:
            var_names: 变量名列表

        Returns:
            {'found': [命中变量], 'not_found': [未命中变量]}
        """
        found = []
        not_found = []

        for var_name in var_names:
            if var_name in self._metadata.variables:
                found.append(var_name)
            else:
                not_found.append(var_name)

        return {'found': found, 'not_found': not_found}

    def find_ambiguous_variables(self, var_names: List[str]) -> Dict[str, List[str]]:
        """查找能同时匹配多张表的变量（歧义变量）

        Args:
            var_names: 变量名列表

        Returns:
            {歧义变量名: [匹配的表名列表]}
        """
        ambiguous: Dict[str, List[str]] = {}

        for var_name in var_names:
            appears_in = []
            for tbl_name, tbl_meta in self._metadata.tables.items():
                if var_name in tbl_meta.variables:
                    appears_in.append(tbl_name)

            if len(appears_in) > 1:
                ambiguous[var_name] = appears_in

        return ambiguous

    def find_variable_sources(self, var_name: str) -> List[str]:
        """查找变量所在的所有来源表

        Args:
            var_name: 变量名

        Returns:
            包含该变量的所有表名列表
        """
        tables = []
        for tbl_name, tbl_meta in self._metadata.tables.items():
            if var_name in tbl_meta.variables:
                tables.append(tbl_name)
        return tables
