"""子查询构建模块

职责：
1. 单表子查询构建（带分区控制、时间区间匹配、额外WHERE条件）
2. 多表JOIN构建（同join_key的表合并）
3. ON条件构建（支持时间区间匹配、自定义JOIN条件）
4. 样本表CTE构建
5. 分组CTE构建
6. 通用ON条件构建（用于临时表方式）
"""
from typing import List, Optional

from src.metadata.manager import MetadataManager
from src.core.config_loader import SQLConfig
from src.core.models import TableGroup


class SubqueryBuilder:
    """子查询构建器：构建单表/多表子查询和ON条件"""

    INDENT = "    "

    def __init__(self, metadata_manager: MetadataManager,
                 sql_config: Optional[SQLConfig] = None):
        self.metadata = metadata_manager
        self.config = sql_config or SQLConfig()

    def _indent(self, sql: str, level: int = 1) -> str:
        """SQL缩进"""
        indent = self.INDENT * level
        return "\n".join([indent + line for line in sql.split("\n")])

    # ==================== 单表子查询 ====================

    def build_single_table_subquery(self, table_name: str,
                                     variables: List[str],
                                     join_key: str,
                                     sample_table: str,
                                     bridge_key: str) -> str:
        """构建单表子查询

        Args:
            table_name: 变量表名（可能包含 $platform 占位符）
            variables: 变量列表
            join_key: 变量表的关联键
            sample_table: 样本表名
            bridge_key: 样本表中用于桥接的字段（通常等于join_key）
        """
        # 解析表名（替换 $platform 占位符）
        resolved_table_name = self.config.resolve_table_name(table_name)

        table_meta = self.metadata.get_table(table_name)
        partition_field = table_meta.partition_field if table_meta else "dt"
        category = table_meta.category if table_meta else ""
        platform = table_meta.platform if table_meta else ""

        # 检查是否配置了时间区间匹配（跨月份匹配不需要限制partition_field = biz_date）
        time_config = self.config.get_time_range_config(table_name)
        is_time_range_table = time_config is not None

        # 获取分区控制策略配置
        partition_config = self.config.get_partition_config(table_name, category, platform)
        partition_strategy = partition_config.get('strategy', 'equality')
        partition_control_field = partition_config.get('partition_field', partition_field)

        # 字段去重
        unique_vars = list(dict.fromkeys(variables))
        # 使用数据库实际列名构建SELECT字段，但AS使用模型变量名
        # 征信变量：join_key 统一 AS 为 ci_rpt_id，便于后续合并表统一关联
        if bridge_key == 'ci_rpt_id':
            select_fields = [f"t.{join_key} AS ci_rpt_id", f"t.{partition_field}"]
        else:
            select_fields = [f"t.{join_key}", f"t.{partition_field}"]

        # 如果配置了时间区间匹配且需要去重，额外输出格式化后的时间字段
        formatted_time_field = None
        if time_config and time_config.get('dedup'):
            time_expr_template = time_config.get('time_expr', '{field}')
            time_field = time_config.get('time_field', 'dt')
            output_time_field = time_config.get('output_time_field', f'formatted_{time_field}')
            formatted_time_expr = time_expr_template.format(field=f"t.{time_field}")
            select_fields.append(f"{formatted_time_expr} AS {output_time_field}")
            formatted_time_field = output_time_field

        for var in unique_vars:
            db_col = self._get_db_column_name(var)
            if db_col != var:
                select_fields.append(f"t.{db_col} AS {var}")
            else:
                select_fields.append(f"t.{var}")
        fields_str = ", ".join(select_fields)

        # 构建WHERE条件
        where_conditions = []

        # 根据分区策略生成分区条件
        if partition_strategy == 'range':
            # range策略：使用分区范围限制（如 part_id >= 202512）
            min_partition = partition_config.get('min_partition')
            if min_partition:
                where_conditions.append(f"t.{partition_control_field} >= {min_partition}")
        elif not is_time_range_table:
            # equality策略（默认）：等值匹配 t.partition_field = '${biz_date}'
            # 时间区间匹配模式（equality/range）不限制 partition_field = '${biz_date}'，允许跨月份匹配
            where_conditions.append(f"t.{partition_control_field} = '${{biz_date}}'")

        where_conditions.append(
            f"t.{join_key} IN (\n"
            f"      SELECT {bridge_key} FROM {sample_table}\n"
            f"  )"
        )

        # 添加额外的WHERE条件（从配置读取）
        extra_conditions = self.config.get_extra_where_conditions(
            category, platform, table_name
        )
        for cond in extra_conditions:
            where_conditions.append(cond)

        where_clause = "\n  AND ".join(where_conditions)

        return f"SELECT {fields_str}\nFROM {resolved_table_name} t\nWHERE {where_clause}"

    # ==================== 多表JOIN ====================

    def build_multi_table_join(self, group: TableGroup,
                                sample_table: str, bridge_key: str) -> str:
        """构建多表JOIN（同join_key的表合并）

        支持时间区间匹配：为配置了 time_range_joins 的表生成特殊的ON条件
        """
        tables = group.tables
        first_table = tables[0]

        # 构建别名映射
        alias_map = {first_table: 'a'}
        for idx, t in enumerate(tables[1:], start=2):
            alias_map[t] = chr(ord('a') + idx - 1)

        # 构建SELECT字段（处理重复变量）
        select_parts = [f"a.{group.join_key}"]

        seen_vars = {group.join_key}
        for t in tables:
            alias = alias_map[t]
            for var in group.table_vars[t]:
                db_col = self._get_db_column_name(var)
                if var in seen_vars:
                    # 重复变量：使用数据库列名，AS用别名前缀+变量名
                    select_parts.append(f"{alias}.{db_col} AS {alias}_{var}")
                else:
                    if db_col != var:
                        select_parts.append(f"{alias}.{db_col} AS {var}")
                    else:
                        select_parts.append(f"{alias}.{var}")
                    seen_vars.add(var)

        lines = ["SELECT"]
        lines.append(",\n".join([f"    {p}" for p in select_parts]))

        # FROM + JOIN
        first_subquery = self.build_single_table_subquery(
            first_table, group.table_vars[first_table],
            group.join_key, sample_table, bridge_key
        )
        lines.append(f"FROM (")
        lines.append(self._indent(first_subquery))
        lines.append(f") a")

        for t in tables[1:]:
            alias = alias_map[t]
            subquery = self.build_single_table_subquery(
                t, group.table_vars[t],
                group.join_key, sample_table, bridge_key
            )
            # 构建ON条件（支持时间区间匹配）
            on_clause = self.build_table_on_clause(
                t, alias, 'a', group.join_key
            )
            lines.append(f"LEFT JOIN (")
            lines.append(self._indent(subquery))
            lines.append(f") {alias} ON {on_clause}")

        return "\n".join(lines)

    # ==================== ON条件构建 ====================

    def build_table_on_clause(self, table_name: str, table_alias: str,
                               base_alias: str, join_key: str) -> str:
        """构建单张表的ON条件（支持时间区间匹配和等号匹配）"""
        # 基础等值条件
        base_condition = f"{base_alias}.{join_key} = {table_alias}.{join_key}"

        # 检查是否配置了时间区间匹配
        time_config = self.config.get_time_range_config(table_name)
        if not time_config:
            # 无时间匹配配置，仅使用join_key等值关联
            # 各子查询已通过WHERE独立限制分区范围，无需额外关联分区字段
            return base_condition

        # 判断匹配模式：equality（等号）或 range（范围，默认）
        match_mode = time_config.get('match_mode', 'range')

        # 构建时间字段表达式
        time_field = time_config.get('time_field', 'part_id')
        sample_time_field = time_config.get('sample_time_field', 'issue_time')
        time_expr_template = time_config.get('time_expr', '{field}')
        sample_expr_template = time_config.get('sample_expr', '{field}')

        table_time_expr = time_expr_template.format(field=f"{table_alias}.{time_field}")
        sample_time_expr = sample_expr_template.format(field=f"{base_alias}.{sample_time_field}")

        if match_mode == 'equality':
            # 等号匹配模式：如 part_id+1月 = issue_time月份
            time_condition = f"{table_time_expr} = {sample_time_expr}"
            return f"{base_condition}\n  AND {time_condition}"
        else:
            # 范围匹配模式（默认）：如 part_id <= issue_time，且窗口内
            direction = time_config.get('direction', '<=')
            window = time_config.get('window', 1)
            time_function = time_config.get('time_function', 'DATEDIFF')

            # 构建时间条件
            time_condition = f"{table_time_expr} {direction} {sample_time_expr}"

            # 构建窗口条件
            if time_function == 'MONTHS_BETWEEN':
                window_condition = (
                    f"MONTHS_BETWEEN({sample_time_expr}, {table_time_expr}) <= {window}"
                )
            else:
                window_condition = (
                    f"DATEDIFF({sample_time_expr}, {table_time_expr}) <= {window}"
                )

            return f"{base_condition}\n  AND {time_condition}\n  AND {window_condition}"

    def build_on_clause(self, table_name: str, table_alias: str,
                         sample_alias: str, join_key: str,
                         bridge_key: str) -> str:
        """构建ON条件（支持自定义JOIN条件和时间区间匹配）

        支持：
        1. 标准JOIN：s.bridge_key = alias.join_key
        2. MD5转换：s.bridge_key = MD5(alias.join_key)
        3. 时间偏移：s.time_field = to_char(to_date(alias.time_field) - offset, 'yyyyMMdd')
        4. 时间区间匹配：MONTHS_BETWEEN / DATEDIFF
        5. 自定义ON条件：完全覆盖
        """
        # 检查是否有完全自定义的ON条件（最高优先级）
        custom_config = self.config.get_custom_join_config(table_name)
        if custom_config and custom_config.get('custom_on_clause'):
            return custom_config['custom_on_clause']

        # 获取关联键（可能被自定义配置覆盖）
        actual_join_key = custom_config.get('join_key', join_key) if custom_config else join_key
        actual_sample_key = custom_config.get('sample_key', bridge_key) if custom_config else bridge_key

        # 构建基础JOIN条件
        if custom_config and custom_config.get('md5_transform', False):
            # MD5转换：样本字段 = MD5(表字段)
            join_condition = (
                f"{sample_alias}.{actual_sample_key} = "
                f"MD5({table_alias}.{actual_join_key})"
            )
        else:
            join_condition = (
                f"{sample_alias}.{actual_sample_key} = "
                f"{table_alias}.{actual_join_key}"
            )

        # 添加时间偏移条件（来自 custom_join_conditions）
        if custom_config:
            time_offset = custom_config.get('time_offset')
            if time_offset:
                field = time_offset.get('field', 'issue_time')
                offset_days = time_offset.get('offset_days', 0)
                target_field = time_offset.get('target_field', 'data_dt')
                target_expr = time_offset.get('target_expr')

                if target_expr:
                    # 使用自定义表达式
                    expr = target_expr.format(field=f"{sample_alias}.{field}")
                    time_condition = f"{table_alias}.{target_field} = {expr}"
                else:
                    # 默认表达式
                    if offset_days < 0:
                        time_condition = (
                            f"{table_alias}.{target_field} = "
                            f"cast(to_char(to_date({sample_alias}.{field}, 'yyyyMMdd') {offset_days}, "
                            f"'yyyyMMdd') AS int)"
                        )
                    else:
                        time_condition = (
                            f"{table_alias}.{target_field} = "
                            f"cast(to_char(to_date({sample_alias}.{field}, 'yyyyMMdd') + {offset_days}, "
                            f"'yyyyMMdd') AS int)"
                        )

                join_condition = f"{join_condition}\n  AND {time_condition}"

        # 添加时间区间匹配条件（来自 time_range_joins）
        time_range_config = self.config.get_time_range_config(table_name)
        if time_range_config:
            match_mode = time_range_config.get('match_mode', 'range')
            time_field = time_range_config.get('time_field', 'part_id')
            sample_time_field = time_range_config.get('sample_time_field', 'issue_time')
            time_expr_template = time_range_config.get('time_expr', '{field}')
            sample_expr_template = time_range_config.get('sample_expr', '{field}')

            # 替换时间字段表达式
            table_time_expr = time_expr_template.format(field=f"{table_alias}.{time_field}")
            sample_time_expr = sample_expr_template.format(field=f"{sample_alias}.{sample_time_field}")

            if match_mode == 'equality':
                # 等号匹配模式：如 part_id+1月 = issue_time月份
                time_condition = f"{table_time_expr} = {sample_time_expr}"
                join_condition = f"{join_condition}\n  AND {time_condition}"
            else:
                # 范围匹配模式（默认）：如 part_id <= issue_time，且窗口内
                direction = time_range_config.get('direction', '<=')
                window = time_range_config.get('window', 1)
                time_function = time_range_config.get('time_function', 'DATEDIFF')

                if direction == 'between':
                    # between 模式：MONTHS_BETWEEN(...) BETWEEN 0 AND window
                    if time_function == 'MONTHS_BETWEEN':
                        time_condition = (
                            f"MONTHS_BETWEEN({sample_time_expr}, {table_time_expr}) "
                            f"BETWEEN 0 AND {window}"
                        )
                    else:
                        time_condition = (
                            f"DATEDIFF({sample_time_expr}, {table_time_expr}) "
                            f"BETWEEN 0 AND {window}"
                        )
                    join_condition = f"{join_condition}\n  AND {time_condition}"
                else:
                    # 构建时间条件
                    time_condition = f"{table_time_expr} {direction} {sample_time_expr}"

                    # 构建窗口条件
                    if time_function == 'MONTHS_BETWEEN':
                        window_condition = (
                            f"MONTHS_BETWEEN({sample_time_expr}, {table_time_expr}) <= {window}"
                        )
                    else:
                        window_condition = (
                            f"DATEDIFF({sample_time_expr}, {table_time_expr}) <= {window}"
                        )

                    join_condition = f"{join_condition}\n  AND {time_condition}\n  AND {window_condition}"

        return join_condition

    # ==================== CTE构建 ====================

    def build_sample_cte(self, plan) -> str:
        """构建样本表CTE（去重+保留桥接字段）"""
        fields = [plan.sample_key] + [f for f in plan.sample_fields if f != plan.sample_key]
        # 添加桥接字段
        bridge_fields = list(set(plan.bridge_keys.values()))
        for bf in bridge_fields:
            if bf not in fields:
                fields.append(bf)

        fields_str = ", ".join([f"{plan.sample_key}"] + fields[1:])

        return f"""SELECT {fields_str}
FROM {plan.sample_table}
WHERE dt = '${{biz_date}}'"""

    def build_group_cte(self, group: TableGroup,
                         sample_table: str, bridge_key: str) -> str:
        """构建单个分组的CTE SQL"""
        if len(group.tables) == 1:
            # 单表：直接子查询
            table_name = group.tables[0]
            variables = group.table_vars[table_name]
            return self.build_single_table_subquery(
                table_name, variables, group.join_key, sample_table, bridge_key
            )

        # 多表：JOIN合并
        return self.build_multi_table_join(group, sample_table, bridge_key)

    # ==================== 辅助方法 ====================

    def _get_db_column_name(self, var_name: str) -> str:
        """获取变量的数据库实际列名"""
        var_meta = self.metadata.get_variable(var_name)
        if var_meta and var_meta.db_column_name and var_meta.db_column_name != var_name:
            return var_meta.db_column_name
        return var_name
