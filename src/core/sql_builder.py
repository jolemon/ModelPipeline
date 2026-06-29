"""
SQL构建器核心模块（Facade模式）

⚠️ 架构说明（Phase 1 重构后）：
本文件仅保留 SQLBuilder Facade类，将具体职责委托给 src.core.sql 子模块：
- SubqueryBuilder: 子查询构建（单表/多表/CTE/ON条件）
- CreditGroupHandler: 征信分组处理（桥接表/征信临时表）
- FieldCollector: 字段收集与映射（SELECT字段/列名映射）
- MergeTableBuilder: 合并表构建（组内合并表SQL）
- SQLFormatter: SQL格式化与输出（最终SELECT/缩进/保存）

功能：
1. CTE临时表生成：同join_key的表在CTE内JOIN合并
2. 样本表桥接：以apply_no样本表为桥梁，关联不同join_key的CTE
3. 重复字段处理：识别跨表重复变量，自动添加表别名前缀
4. 空值填充：外部数据匹配不上时用COALESCE填充
5. 临时表命名：tmp_${work_no}_${date}_${model_id}_${var_type}_${seq}
6. 子查询拆分：超过max_subquery_join时自动拆分为多个临时表

核心设计：
- 一级分组：按 (platform, join_key) → 生成CTE临时表
- 二级关联：样本表 LEFT JOIN 各CTE（通过不同关联键）
- 重复处理：同名变量自动重命名为 {table_alias}_{var_name}
- 命名规范：全部英文，从config.yaml读取配置
"""
from typing import List, Dict, Optional, Union
from pathlib import Path

from src.metadata.manager import MetadataManager
from src.core.config_loader import SQLConfig
from src.core.models import TableGroup, JoinPlan, OutputConfig
from src.core.join_planner import JoinPlanner
from src.core.sql import (
    SubqueryBuilder,
    CreditGroupHandler,
    FieldCollector,
    MergeTableBuilder,
    SQLFormatter,
)


class SQLBuilder:
    """
    SQL构建器（Facade模式）

    生成Hive SQL脚本，支持：
    - CTE(WITH) 方式：更现代，可读性好
    - 临时表方式：传统CREATE TABLE，适合调度执行
    - 英文命名规范：从config.yaml读取配置
    """

    INDENT = "    "

    def __init__(self, metadata_manager: MetadataManager,
                 sql_config: Optional[SQLConfig] = None):
        """初始化SQL构建器。

        Args:
            metadata_manager: 元数据管理器，提供变量和表的元数据查询
            sql_config: SQL生成配置（可选，默认使用SQLConfig默认配置）
        """
        self.metadata = metadata_manager
        self.config = sql_config or SQLConfig()
        self.planner = JoinPlanner(metadata_manager, self.config)

        # 初始化子组件
        self._subquery = SubqueryBuilder(metadata_manager, self.config)
        self._credit = CreditGroupHandler(metadata_manager, self.config, self._subquery)
        self._fields = FieldCollector(metadata_manager, self.config)
        self._merge = MergeTableBuilder(self.config)
        self._formatter = SQLFormatter(self.config, self._fields)

    # ==================== 核心生成方法 ====================

    def build_cte_sql(self, model_features: List[str],
                      sample_config: dict,
                      output_config: OutputConfig) -> str:
        """
        生成CTE(WITH)风格的完整SQL
        """
        plan = self.planner.plan(
            model_features=model_features,
            sample_table=sample_config['table_name'],
            sample_key=sample_config.get('key', 'apply_no'),
            sample_fields=sample_config.get('fields', [sample_config.get('key', 'apply_no')])
        )

        lines = []

        # 1. CTE定义
        cte_parts = []

        # 样本表CTE（去重+标准化）
        sample_cte = self._subquery.build_sample_cte(plan)
        cte_parts.append(f"sample AS (\n{self._indent(sample_cte)}\n)")

        # 各分组CTE
        for group in plan.groups:
            bridge_key = plan.bridge_keys[group.group_id]
            group_cte = self._subquery.build_group_cte(group, plan.sample_table, bridge_key)
            cte_parts.append(f"{group.group_id} AS (\n{self._indent(group_cte)}\n)")

        lines.append("WITH")
        lines.append(",\n".join(cte_parts))

        # 2. 最终SELECT
        lines.append(self._formatter.build_final_select(plan, output_config))

        return "\n".join(lines) + ";"

    def build_temp_table_sql(self, model_features: List[str],
                             sample_config: dict,
                             output_config: OutputConfig) -> str:
        """
        生成临时表风格的完整SQL（适合调度执行）

        生成多级CREATE TABLE：
        1. CREATE TABLE tmp_xxx AS ...（征信桥接表，如需要）
        2. CREATE TABLE tmp_xxx AS ...（各分组临时表）
        3. CREATE TABLE output AS ...（最终关联）
        """
        plan = self.planner.plan(
            model_features=model_features,
            sample_table=sample_config['table_name'],
            sample_key=sample_config.get('key', 'apply_no'),
            sample_fields=sample_config.get('fields', [sample_config.get('key', 'apply_no')])
        )

        sql_parts = []

        # 0. 如果启用征信桥接表配置，先生成全局征信桥接表
        credit_groups = [g for g in plan.groups if self._credit.is_credit_group(g)]
        if credit_groups and self.config.credit_bridge_enabled:
            bridge_sql = self._credit.build_credit_bridge_table(
                plan.sample_table, plan.sample_key
            )
            if bridge_sql:
                sql_parts.append(bridge_sql)
                sql_parts.append("")

        # 1. 生成各分组临时表
        for group in plan.groups:
            bridge_key = plan.bridge_keys[group.group_id]
            temp_sql = self._build_group_temp_table(
                group, plan.sample_table, bridge_key, plan.sample_key, plan.sample_alias
            )
            sql_parts.append(f"-- ===== {group.platform} 临时表 ({group.join_key}) [{group.group_id}] =====")
            sql_parts.append(temp_sql)
            sql_parts.append("")

        # 2. 如果启用组内合并，生成合并表
        merge_tables = {}  # {group_id: 合并后的临时表名}
        if self.config.group_merge:
            merge_sql_parts = self._merge.build_group_merge_tables(plan)
            if merge_sql_parts:
                sql_parts.append("-- ===== 组内合并表 =====")
                sql_parts.extend(merge_sql_parts)
                sql_parts.append("")
                # 获取合并表映射
                merge_tables = self._merge.get_merge_table_mapping(plan)

        # 3. 生成最终关联SQL
        final_sql = self._formatter.build_final_join(plan, output_config, merge_tables)
        sql_parts.append(f"-- ===== 最终输出表 =====")
        sql_parts.append(final_sql)

        return "\n".join(sql_parts)

    # ==================== 临时表构建方法（保留在Facade中） ====================

    def _build_group_temp_table(self, group: TableGroup,
                                 sample_table: str, bridge_key: str,
                                 sample_key: str = "apply_no",
                                 sample_alias: str = "s") -> str:
        """构建单个分组的临时表 SQL (CREATE TABLE AS SELECT)

        新需求：
        1. 非征信变量：使用输入表作为左表，LEFT JOIN各变量表子查询
        2. 征信变量：先创建桥接表，再基于桥接表LEFT JOIN各征信表
        """
        # 判断是否为征信变量分组
        is_credit = self._credit.is_credit_group(group)

        if is_credit:
            return self._credit.build_credit_group_temp_table(
                group, sample_table, bridge_key, sample_key, sample_alias
            )

        # 非征信变量：使用输入表作为左表
        return self._build_non_credit_group_temp_table(
            group, sample_table, bridge_key, sample_key, sample_alias
        )

    def _build_non_credit_group_temp_table(self, group: TableGroup,
                                            sample_table: str,
                                            bridge_key: str,
                                            sample_key: str,
                                            sample_alias: str = "s") -> str:
        """构建非征信变量分组的临时表（输入表LEFT JOIN各变量表）

        支持自定义JOIN条件（MD5转换、时间偏移等）和JOIN类型配置
        支持时间区间匹配后的去重（ROW_NUMBER窗口函数）
        """
        # 获取该组的JOIN类型
        category = self._fields.get_category_for_platform(group.platform)
        join_type = self.config.get_join_type(category, group.platform)

        # 检测该组是否包含需要去重的表
        dedup_configs = []
        for t in group.tables:
            time_config = self.config.get_time_range_config(t)
            if time_config and time_config.get('dedup'):
                dedup_configs.append((t, time_config))

        needs_dedup = len(dedup_configs) > 0

        lines = [f"DROP TABLE IF EXISTS {group.temp_table_name};"]
        lines.append(f"CREATE TABLE {group.temp_table_name} AS")

        # 如果需要去重，在外层包装 ROW_NUMBER()
        if needs_dedup:
            lines.append("SELECT * FROM (")
            lines.append("SELECT")
            lines.append("    *,")
            # 使用第一个去重配置生成 ROW_NUMBER()
            # 支持 ${sample_key} 占位符替换为实际的 sample_key
            dedup_table, dedup_config = dedup_configs[0]
            partition_by = dedup_config.get('dedup_partition_by', '${sample_key}')
            partition_by = partition_by.replace('${sample_key}', sample_key)
            order_by = dedup_config.get('dedup_order_by', '1')
            lines.append(f"    ROW_NUMBER() OVER (PARTITION BY {partition_by} ORDER BY {order_by}) AS rn")
            lines.append("FROM (")

        # 构建SELECT字段（去掉冗余的 AS 别名）
        select_parts = [f"{sample_alias}.{sample_key}"]

        # 如果bridge_key不等于sample_key，也保留bridge_key
        if bridge_key != sample_key:
            select_parts.append(f"{sample_alias}.{bridge_key}")

        # 添加各表变量
        alias_map = {}
        for idx, t in enumerate(group.tables, start=1):
            alias_map[t] = chr(ord('a') + idx - 1)

        seen_vars = {sample_key, bridge_key}
        for t in group.tables:
            alias = alias_map[t]
            for var in group.table_vars[t]:
                db_col = self._fields.get_db_column_name(var)
                if var in seen_vars:
                    # 重复变量：使用数据库列名，AS用别名前缀+变量名
                    select_parts.append(f"{alias}.{db_col} AS {alias}_{var}")
                else:
                    if db_col != var:
                        select_parts.append(f"{alias}.{db_col} AS {var}")
                    else:
                        select_parts.append(f"{alias}.{var}")
                    seen_vars.add(var)

        if needs_dedup:
            inner_lines = ["SELECT"]
            inner_lines.append(",\n".join([f"    {p}" for p in select_parts]))
        else:
            lines.append("SELECT")
            lines.append(",\n".join([f"    {p}" for p in select_parts]))

        # FROM：输入表
        from_lines = [f"FROM {sample_table} {sample_alias}"]

        # JOIN各变量表子查询（支持自定义JOIN条件）
        for t in group.tables:
            alias = alias_map[t]
            subquery = self._subquery.build_single_table_subquery(
                t, group.table_vars[t],
                group.join_key, sample_table, bridge_key
            )

            # 构建ON条件（支持自定义JOIN）
            on_clause = self._subquery.build_on_clause(
                t, alias, sample_alias, group.join_key, bridge_key
            )

            from_lines.append(f"{join_type} (")
            from_lines.append(self._indent(subquery))
            from_lines.append(f") {alias} ON {on_clause}")

        if needs_dedup:
            inner_lines.extend(from_lines)
            inner_sql = "\n".join(inner_lines)
            lines.append(self._indent(inner_sql, level=1))
            lines.append(")")
            lines.append("WHERE rn = 1")
            lines.append(")")
        else:
            lines.extend(from_lines)

        return "\n".join(lines) + ";"

    # ==================== 公共方法委托 ====================

    def save_sql(self, sql: str, output_path: Union[str, Path]) -> None:
        """保存SQL到文件"""
        self._formatter.save_sql(sql, output_path)

    def generate_execution_summary(self, plan: JoinPlan) -> str:
        """生成执行计划摘要（用于日志/文档）"""
        return self._formatter.generate_execution_summary(plan)

    # ==================== 辅助方法 ====================

    def _indent(self, sql: str, level: int = 1) -> str:
        """SQL缩进"""
        indent = self.INDENT * level
        return "\n".join([indent + line for line in sql.split("\n")])
