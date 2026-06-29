"""
输出配置模块

职责：输出表配置 + 样本表配置
"""

from typing import Dict, List, Optional, Any


class OutputConfig:
    """输出配置：输出表设置 + 样本表设置"""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    @property
    def output_table_name(self) -> str:
        """输出表名"""
        return self._config.get('output', {}).get('table_name', '')

    @property
    def output_database(self) -> str:
        """输出数据库"""
        return self._config.get('output', {}).get('database', '')

    @property
    def output_partition_clause(self) -> str:
        """输出表分区语句"""
        return self._config.get('output', {}).get('partition_clause', '')

    @property
    def output_include_sample_fields(self) -> bool:
        """是否在打分表中包含样本表额外字段"""
        return self._config.get('output', {}).get('include_sample_fields', True)

    @property
    def output_variable_enabled(self) -> bool:
        """是否在打分表中输出模型变量字段"""
        return self._config.get('output', {}).get('variable_output', {}).get('enabled', False)

    @property
    def output_variable_sort_by_importance(self) -> bool:
        """变量字段是否按重要度排序"""
        return self._config.get('output', {}).get('variable_output', {}).get('sort_by_importance', True)

    @property
    def output_variable_top_n(self) -> int:
        """变量字段输出数量限制，0表示全部"""
        return self._config.get('output', {}).get('variable_output', {}).get('top_n', 0)

    @property
    def output_keep_columns(self) -> List[str]:
        """输出表保留列（主键等）"""
        return self._config.get('output', {}).get('keep_columns', ['apply_no']) or ['apply_no']

    @property
    def sample_table_name(self) -> str:
        """样本表名"""
        return self._config.get('sample', {}).get('table_name', '')

    @property
    def sample_key(self) -> str:
        """样本表关联主键"""
        return self._config.get('sample', {}).get('key', 'apply_no')

    @property
    def sample_fields(self) -> List[str]:
        """样本表保留字段列表"""
        return self._config.get('sample', {}).get('fields', []) or []
