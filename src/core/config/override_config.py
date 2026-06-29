"""
覆盖配置模块

职责：变量覆盖 + 表关联键覆盖 + 变量别名 + 黑名单
"""

from typing import Dict, List, Optional, Any


class OverrideConfig:
    """覆盖配置：变量覆盖、表关联键覆盖、变量别名、黑名单"""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    @property
    def variable_overrides(self) -> Dict[str, Dict[str, str]]:
        """变量覆盖配置 {变量名: {source_table: ...}}"""
        return self._config.get('variable_overrides', {}) or {}

    def get_variable_override(self, var_name: str) -> Optional[Dict[str, str]]:
        """获取单个变量的覆盖配置"""
        return self.variable_overrides.get(var_name)

    @property
    def table_join_keys(self) -> Dict[str, Dict[str, str]]:
        """各表关联键覆盖配置 {表名: {join_key: ..., partition_field: ...}}"""
        return self._config.get('table_join_keys', {}) or {}

    def get_table_join_config(self, table_name: str) -> Optional[Dict[str, str]]:
        """获取单张表的关联键覆盖配置"""
        return self.table_join_keys.get(table_name)

    @property
    def variable_aliases(self) -> Dict[str, str]:
        """变量名别名映射配置 {模型变量名: 数据库列名}"""
        return self._config.get('variable_aliases', {}) or {}

    def get_variable_alias(self, var_name: str) -> Optional[str]:
        """获取单个变量的数据库列名别名"""
        return self.variable_aliases.get(var_name)

    def has_variable_alias(self, var_name: str) -> bool:
        """检查变量是否配置了别名映射"""
        return var_name in self.variable_aliases

    @property
    def blacklist_vars(self) -> List[str]:
        """禁用变量黑名单"""
        return self._config.get('blacklist_vars', []) or []

    def is_blacklisted(self, var_name: str) -> bool:
        """检查变量是否在黑名单中"""
        return var_name in self.blacklist_vars

    def check_blacklist(self, features: List[str]) -> List[str]:
        """检查变量列表中的黑名单命中情况"""
        return [v for v in features if v in self.blacklist_vars]
