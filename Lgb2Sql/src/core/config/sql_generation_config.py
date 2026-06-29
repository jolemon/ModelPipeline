"""
SQL生成配置模块

职责：SQL生成参数 + JOIN策略 + 分区控制 + 时间区间 + 额外WHERE条件 + 自定义JOIN条件
"""

from typing import Dict, List, Optional, Any


class SQLGenerationConfig:
    """SQL生成配置：子查询参数、JOIN策略、分区控制、额外条件"""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    @property
    def max_subquery_join(self) -> int:
        """最大子查询关联数"""
        return self._config.get('sql_generation', {}).get('max_subquery_join', 3)

    @property
    def subgroup_strategy(self) -> str:
        """子查询分组策略: 'sequential' | 'balanced'"""
        return self._config.get('sql_generation', {}).get('subgroup_strategy', 'balanced')

    @property
    def coalesce_value(self):
        """空值填充值"""
        return self._config.get('sql_generation', {}).get('coalesce_value', -999999)

    @property
    def partition_field(self) -> str:
        """分区字段"""
        return self._config.get('sql_generation', {}).get('partition_field', 'dt')

    @property
    def partition_var(self) -> str:
        """分区变量名"""
        return self._config.get('sql_generation', {}).get('partition_var', '${biz_date}')

    @property
    def group_merge(self) -> bool:
        """是否启用组内合并"""
        return self._config.get('sql_generation', {}).get('group_merge', False)

    @property
    def naming_style(self) -> str:
        """临时表命名风格: 'simple' | 'descriptive'"""
        return self._config.get('sql_generation', {}).get('naming_style', 'simple')

    @property
    def credit_platforms(self) -> List[str]:
        """征信平台列表（使用PBCI桥接表机制的平台）"""
        return self._config.get('sql_generation', {}).get('credit_platforms', [
            "征信变量-总行",
            "征信变量-消金"
        ])

    @property
    def join_types(self) -> Dict[str, Dict[str, str]]:
        """JOIN类型配置 {by_category: {...}, by_platform: {...}}"""
        return self._config.get('sql_generation', {}).get('join_types', {})

    def get_join_type(self, category: str, platform: str) -> str:
        """获取指定分类/平台的JOIN类型

        优先级：by_platform > by_category > 默认LEFT JOIN
        """
        by_platform = self.join_types.get('by_platform', {})
        if platform in by_platform:
            return by_platform[platform]

        by_category = self.join_types.get('by_category', {})
        if category in by_category:
            return by_category[category]

        return 'LEFT JOIN'

    @property
    def partition_control(self) -> Dict[str, Any]:
        """分区控制策略配置"""
        return self._config.get('sql_generation', {}).get('partition_control', {}) or {}

    def get_partition_config(self, table_name: str, category: str,
                              platform: str) -> Dict[str, Any]:
        """获取指定表的分区控制配置（按优先级选择最高级别）"""
        default_config = self.partition_control.get('default') or {}

        by_table = self.partition_control.get('by_table') or {}
        if table_name in by_table:
            config = dict(by_table[table_name])
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config

        by_platform = self.partition_control.get('by_platform') or {}
        if platform in by_platform:
            config = dict(by_platform[platform])
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config

        by_category = self.partition_control.get('by_category') or {}
        if category in by_category:
            config = dict(by_category[category])
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config

        return dict(default_config) if default_config else {
            'strategy': 'equality',
            'partition_field': 'dt'
        }

    @property
    def time_range_joins(self) -> Dict[str, Dict[str, Any]]:
        """时间区间匹配配置"""
        return self._config.get('time_range_joins', {}) or {}

    def get_time_range_config(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取单张表的时间区间匹配配置"""
        return self.time_range_joins.get(table_name)

    def is_time_range_table(self, table_name: str) -> bool:
        """检查表是否配置了时间区间匹配"""
        return table_name in self.time_range_joins

    @property
    def extra_where_conditions(self) -> Dict[str, Dict[str, List[str]]]:
        """额外WHERE条件配置 {by_category: {...}, by_platform: {...}, by_table: {...}}"""
        return self._config.get('extra_where_conditions', {}) or {}
    def get_extra_where_conditions(self, category: str, platform: str,
                                    table_name: str) -> List[str]:
        """获取指定表应该应用的额外WHERE条件（按优先级选择最高级别）"""
        by_table = self.extra_where_conditions.get('by_table') or {}
        if table_name in by_table:
            return list(by_table[table_name])

        by_platform = self.extra_where_conditions.get('by_platform') or {}
        if platform in by_platform:
            return list(by_platform[platform])

        by_category = self.extra_where_conditions.get('by_category') or {}
        if category in by_category:
            return list(by_category[category])

        return []

    @property
    def custom_join_conditions(self) -> Dict[str, Dict[str, Any]]:
        """自定义JOIN条件配置 {by_table: {...}}"""
        return self._config.get('custom_join_conditions', {}).get('by_table', {})

    def get_custom_join_config(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取单张表的自定义JOIN条件配置"""
        return self.custom_join_conditions.get(table_name)

    def has_custom_join(self, table_name: str) -> bool:
        """检查表是否配置了自定义JOIN条件"""
        return table_name in self.custom_join_conditions
