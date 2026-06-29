"""字段收集与映射模块

职责：
1. 变量名到数据库列名的映射
2. SELECT字段表达式的构建
3. 最终SQL中所有SELECT字段的收集（样本表+各分组）
4. 平台分类判断
"""
from typing import List, Dict, Optional, Set

from src.metadata.manager import MetadataManager
from src.core.config_loader import SQLConfig
from src.core.models import JoinPlan, TableGroup


class FieldCollector:
    """字段收集器：处理变量映射和SELECT字段组装"""

    def __init__(self, metadata_manager: MetadataManager,
                 sql_config: Optional[SQLConfig] = None):
        self.metadata = metadata_manager
        self.config = sql_config or SQLConfig()

    # ==================== 列名映射 ====================

    def get_db_column_name(self, var_name: str) -> str:
        """获取变量的数据库实际列名

        当变量配置了别名映射（db_column_name != var_name）时，
        返回数据库列名；否则返回变量名本身。
        """
        var_meta = self.metadata.get_variable(var_name)
        if var_meta and var_meta.db_column_name and var_meta.db_column_name != var_name:
            return var_meta.db_column_name
        return var_name

    def build_select_field(self, var_name: str, alias: str = "",
                           force_alias: bool = False) -> str:
        """构建SELECT字段表达式，支持列名映射

        当变量配置了 db_column_name 别名时：
        - SELECT 中使用 db_column_name
        - AS 中使用模型变量名（确保下游引用一致）
        """
        db_column = self.get_db_column_name(var_name)
        prefix = f"{alias}." if alias else ""

        if db_column != var_name or force_alias:
            return f"{prefix}{db_column} AS {var_name}"
        return f"{prefix}{var_name}"

    def get_category_for_platform(self, platform: str) -> str:
        """根据平台名获取分类名"""
        if '征信' in platform:
            return '征信变量'
        elif '行为' in platform:
            return '行为变量'
        elif '外数' in platform or '外部' in platform:
            return '外部数据'
        elif '模型' in platform:
            return '模型分'
        else:
            return '其他'

    # ==================== 字段收集 ====================

    def collect_select_fields(self, plan: JoinPlan,
                              alias_prefix: str = "",
                              merge_tables: Optional[Dict[str, str]] = None) -> List[str]:
        """收集最终SELECT语句的所有字段

        提取 _build_final_select 和 _build_final_join 的公共逻辑：
        收集样本表字段 + 各分组字段（处理重复变量别名）。
        支持合并表：同一合并表的所有子组字段使用统一别名。
        """
        select_fields: List[str] = []

        # 样本表字段（使用 sample_alias.* 全选，自动包含样本表所有字段）
        select_fields.append(f"{plan.sample_alias}.*")

        # 按合并表组织group
        merge_groups: Dict[str, List[TableGroup]] = {}
        normal_groups: List[TableGroup] = []

        for group in plan.groups:
            if merge_tables and group.group_id in merge_tables:
                merge_table = merge_tables[group.group_id]
                if merge_table not in merge_groups:
                    merge_groups[merge_table] = []
                merge_groups[merge_table].append(group)
            else:
                normal_groups.append(group)

        # 处理合并表：收集所有子组变量，使用统一别名
        for merge_table, groups in merge_groups.items():
            first_group = groups[0]
            alias = f"{alias_prefix}{first_group.group_id}"

            # 收集所有子组的变量（去重）
            seen_vars: Set[str] = set()
            for group in groups:
                for var in group.all_variables:
                    if var in (plan.sample_key, group.join_key):
                        continue
                    if var in seen_vars:
                        continue
                    seen_vars.add(var)

                    # 处理组内重复变量
                    full_var_name = var
                    if var in group.duplicate_vars:
                        first_table = next(
                            t for t in group.tables if var in group.table_vars[t]
                        )
                        table_alias = chr(ord('a') + group.tables.index(first_table))
                        full_var_name = f"{table_alias}_{var}"

                    select_fields.append(f"{alias}.{full_var_name} AS {var}")

        # 处理普通group
        for group in normal_groups:
            alias = f"{alias_prefix}{group.group_id}"
            for var in group.all_variables:
                if var in (plan.sample_key, group.join_key):
                    continue

                full_var_name = var
                if var in group.duplicate_vars:
                    first_table = next(
                        t for t in group.tables if var in group.table_vars[t]
                    )
                    table_alias = chr(ord('a') + group.tables.index(first_table))
                    full_var_name = f"{table_alias}_{var}"

                select_fields.append(f"{alias}.{full_var_name} AS {var}")

        return select_fields
