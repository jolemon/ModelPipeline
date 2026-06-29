"""SQL格式化与输出模块

职责：
1. 构建最终SELECT语句（CTE方式）
2. 构建最终关联SQL（临时表方式）
3. SQL缩进
4. 保存SQL到文件
5. 生成执行计划摘要
"""
from pathlib import Path
from typing import List, Dict, Optional, Union

from src.core.config_loader import SQLConfig
from src.core.models import JoinPlan, OutputConfig
from src.core.sql.field_collector import FieldCollector


class SQLFormatter:
    """SQL格式化器：处理最终SQL组装和输出"""

    INDENT = "    "

    def __init__(self, sql_config: Optional[SQLConfig] = None,
                 field_collector: Optional[FieldCollector] = None):
        self.config = sql_config or SQLConfig()
        self.fields = field_collector

    def _indent(self, sql: str, level: int = 1) -> str:
        """SQL缩进"""
        indent = self.INDENT * level
        return "\n".join([indent + line for line in sql.split("\n")])

    # ==================== 最终SQL构建 ====================

    def build_final_select(self, plan: JoinPlan,
                           output_config: OutputConfig) -> str:
        """构建最终SELECT语句（CTE方式）"""
        output_table = output_config.output_table
        if output_config.output_db:
            output_table = f"{output_config.output_db}.{output_table}"

        select_fields = self.fields.collect_select_fields(plan, alias_prefix="")

        # 构建SQL
        lines = [f"DROP TABLE IF EXISTS {output_table};"]
        lines.append(f"CREATE TABLE IF NOT EXISTS {output_table} AS")
        lines.append("SELECT")
        lines.append(",\n".join([f"    {f}" for f in select_fields]))

        # FROM + JOIN
        lines.append(f"FROM sample {plan.sample_alias}")
        for group in plan.groups:
            alias = group.group_id
            bridge_key = plan.bridge_keys[group.group_id]
            lines.append(
                f"LEFT JOIN {alias} ON {plan.sample_alias}.{bridge_key} = {alias}.{group.join_key}"
            )

        return "\n".join(lines)

    def build_final_join(self, plan: JoinPlan,
                          output_config: OutputConfig,
                          merge_tables: Optional[Dict[str, str]] = None) -> str:
        """构建最终关联SQL（临时表方式）

        新需求：使用输入表的主键(sample_key)作为最终关联条件
        支持合并表（group_merge）
        """
        output_table = output_config.output_table
        if output_config.output_db:
            output_table = f"{output_config.output_db}.{output_table}"

        select_fields = self.fields.collect_select_fields(
            plan, alias_prefix="t_", merge_tables=merge_tables
        )

        # 构建SQL
        lines = [f"DROP TABLE IF EXISTS {output_table};"]
        lines.append(f"CREATE TABLE IF NOT EXISTS {output_table} AS")
        lines.append("SELECT")
        lines.append(",\n".join([f"    {f}" for f in select_fields]))

        lines.append(f"FROM {plan.sample_table} {plan.sample_alias}")

        # 跟踪已生成的合并表JOIN，避免重复
        seen_merge_tables: set = set()

        for group in plan.groups:
            # 如果该分组有合并表，使用合并表
            if merge_tables and group.group_id in merge_tables:
                merge_table = merge_tables[group.group_id]
                if merge_table in seen_merge_tables:
                    continue  # 该合并表已生成过JOIN，跳过
                seen_merge_tables.add(merge_table)
                temp_table = merge_table
                # 使用当前group_id作为合并表的别名（当前group就是第一个遇到该合并表的group）
                alias = f"t_{group.group_id}"
            else:
                temp_table = group.temp_table_name
                alias = f"t_{group.group_id}"

            # 使用输入表主键作为关联条件（新需求）
            lines.append(
                f"LEFT JOIN {temp_table} {alias} ON {plan.sample_alias}.{plan.sample_key} = {alias}.{plan.sample_key}"
            )

        return "\n".join(lines) + ";"

    # ==================== SQL输出 ====================

    def save_sql(self, sql: str, output_path: Union[str, Path]) -> None:
        """保存SQL到文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(sql)
        print(f"SQL已保存到: {output_path}")

    def generate_execution_summary(self, plan: JoinPlan) -> str:
        """生成执行计划摘要（用于日志/文档）"""
        lines = ["=" * 60]
        lines.append("JOIN执行计划摘要")
        lines.append("=" * 60)
        lines.append(f"样本表: {plan.sample_table}")
        lines.append(f"样本主键: {plan.sample_key}")
        lines.append(f"CTE/临时表分组数: {len(plan.groups)}")
        lines.append("")

        total_tables = 0
        for g in plan.groups:
            total_tables += len(g.tables)
            lines.append(f"  [{g.group_id}]")
            lines.append(f"    平台: {g.platform}")
            lines.append(f"    关联键: {g.join_key}")
            lines.append(f"    包含表: {len(g.tables)}张")
            lines.append(f"    变量数: {len(g.all_variables)}个")
            if g.duplicate_vars:
                lines.append(f"    组内重复变量: {len(g.duplicate_vars)}个")
            lines.append("")

        lines.append(f"总计: {total_tables}张源表 → {len(plan.groups)}个CTE分组")
        lines.append("=" * 60)
        return "\n".join(lines)
