"""合并表构建模块

职责：
1. 构建组内合并表SQL（将同一平台的多张临时表合并为中间总表）
2. 获取合并表映射（{group_id: merged_table_name}）
"""
from typing import List, Dict, Optional

from src.core.config_loader import SQLConfig
from src.core.models import JoinPlan, TableGroup


class MergeTableBuilder:
    """合并表构建器：构建组内合并表SQL"""

    def __init__(self, sql_config: Optional[SQLConfig] = None):
        self.config = sql_config or SQLConfig()

    def build_group_merge_tables(self, plan: JoinPlan) -> List[str]:
        """构建组内合并表SQL

        将同一平台的多张临时表合并为中间总表（不再区分join_key）
        例如：征信变量的所有临时表合并为1个总表
        """
        sql_parts = []

        # 按 platform 分组，找出有多个子组的平台
        platform_groups: Dict[str, List[TableGroup]] = {}
        for group in plan.groups:
            platform = group.platform
            if platform not in platform_groups:
                platform_groups[platform] = []
            platform_groups[platform].append(group)

        # 为有多子组的平台创建合并表
        for platform, groups in platform_groups.items():
            if len(groups) <= 1:
                continue  # 只有一个子组，不需要合并

            # 生成合并表名
            first_group = groups[0]
            merge_table_name = f"{first_group.temp_table_name}_merged"

            # 获取该平台的JOIN类型
            category = self._get_category_for_platform(platform)
            join_type = self.config.get_join_type(category, platform)

            # 判断是否为征信变量平台
            is_credit = '征信' in platform

            # 收集该平台下所有不同的 join_key
            all_join_keys = set(g.join_key for g in groups)
            has_multiple_join_keys = len(all_join_keys) > 1

            # 征信变量统一使用 ci_rpt_id 作为关联键
            # 非征信变量统一使用 sample_key(apply_no) 作为关联键，避免同一客户多笔申请时笛卡尔积
            if is_credit:
                merge_key = 'ci_rpt_id'
            else:
                merge_key = plan.sample_key

            # 收集所有字段（去掉冗余的 AS 别名）
            first_group_id = groups[0].group_id
            all_fields = [f"{first_group_id}.{plan.sample_key}"]

            # 征信变量：统一添加 ci_rpt_id
            if is_credit:
                all_fields.append(f"{first_group_id}.ci_rpt_id")
            else:
                # 非征信变量：如果存在多个 join_key，保留所有 join_key 字段
                if has_multiple_join_keys:
                    for jk in sorted(all_join_keys):
                        if jk != plan.sample_key:
                            all_fields.append(f"{first_group_id}.{jk}")
                else:
                    single_join_key = list(all_join_keys)[0]
                    if single_join_key != plan.sample_key:
                        all_fields.append(f"{first_group_id}.{single_join_key}")

            # 收集各子组字段（处理重复）
            seen_vars = set(all_fields)
            for group in groups:
                for var in group.all_variables:
                    if var == plan.sample_key:
                        continue
                    # 跳过 join_key 字段（已添加）
                    if is_credit and var == 'ci_rpt_id':
                        continue
                    if not is_credit and var in all_join_keys:
                        continue
                    if var in group.duplicate_vars:
                        # 重复变量使用别名
                        first_table = next(
                            t for t in group.tables if var in group.table_vars[t]
                        )
                        table_alias = chr(ord('a') + group.tables.index(first_table))
                        full_var_name = f"{table_alias}_{var}"
                        if full_var_name not in seen_vars:
                            all_fields.append(f"{group.group_id}.{full_var_name} AS {full_var_name}")
                            seen_vars.add(full_var_name)
                    else:
                        if var not in seen_vars:
                            all_fields.append(f"{group.group_id}.{var}")
                            seen_vars.add(var)

            # 构建合并SQL
            lines = [f"DROP TABLE IF EXISTS {merge_table_name};"]
            lines.append(f"CREATE TABLE {merge_table_name} AS")
            lines.append("SELECT")
            lines.append(",\n".join([f"    {f}" for f in all_fields]))

            # FROM + JOIN
            lines.append(f"FROM {groups[0].temp_table_name} {first_group_id}")
            for group in groups[1:]:
                if is_credit:
                    # 征信变量统一使用 ci_rpt_id 关联
                    lines.append(
                        f"{join_type} {group.temp_table_name} {group.group_id} "
                        f"ON {first_group_id}.ci_rpt_id = {group.group_id}.ci_rpt_id"
                    )
                else:
                    # 非征信变量统一使用 sample_key(apply_no) 关联，避免同一客户多笔申请时笛卡尔积
                    lines.append(
                        f"{join_type} {group.temp_table_name} {group.group_id} "
                        f"ON {first_group_id}.{plan.sample_key} = {group.group_id}.{plan.sample_key}"
                    )

            lines.append(";")
            sql_parts.append("\n".join(lines))

        return sql_parts

    def get_merge_table_mapping(self, plan: JoinPlan) -> Dict[str, str]:
        """获取合并表映射

        Returns:
            {group_id: 合并后的表名}，只包含有多个子组的平台
        """
        merge_tables = {}
        platform_groups: Dict[str, List[TableGroup]] = {}
        for group in plan.groups:
            platform = group.platform
            if platform not in platform_groups:
                platform_groups[platform] = []
            platform_groups[platform].append(group)

        for platform, groups in platform_groups.items():
            if len(groups) <= 1:
                continue

            merge_table_name = f"{groups[0].temp_table_name}_merged"
            for group in groups:
                merge_tables[group.group_id] = merge_table_name

        return merge_tables

    def _get_category_for_platform(self, platform: str) -> str:
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
