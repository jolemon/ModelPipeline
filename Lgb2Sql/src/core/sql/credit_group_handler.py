"""征信分组处理模块

职责：
1. 判断分组是否为征信变量分组
2. 构建征信变量分组的临时表（基于桥接表LEFT JOIN各征信表）
3. 构建全局征信桥接表SQL
4. 构建征信主键表子查询
"""
from typing import List, Optional

from src.metadata.manager import MetadataManager
from src.core.config_loader import SQLConfig
from src.core.models import TableGroup
from src.core.sql.subquery_builder import SubqueryBuilder


class CreditGroupHandler:
    """征信分组处理器：处理征信变量分组的SQL构建"""

    INDENT = "    "

    def __init__(self, metadata_manager: MetadataManager,
                 sql_config: Optional[SQLConfig] = None,
                 subquery_builder: Optional[SubqueryBuilder] = None):
        self.metadata = metadata_manager
        self.config = sql_config or SQLConfig()
        self.subquery = subquery_builder or SubqueryBuilder(metadata_manager, sql_config)

    def is_credit_group(self, group: TableGroup) -> bool:
        """判断分组是否为征信变量分组"""
        return group.platform in self.config.credit_platforms

    def build_credit_group_temp_table(self, group: TableGroup,
                                       sample_table: str,
                                       bridge_key: str,
                                       sample_key: str,
                                       sample_alias: str = "s") -> str:
        """构建征信变量分组的临时表（基于桥接表LEFT JOIN各征信表）

        支持自定义JOIN条件（MD5转换、时间偏移等）和JOIN类型配置
        """
        # 判断使用全局桥接表还是分组桥接表
        if self.config.credit_bridge_enabled:
            bridge_table_name = self.config.get_credit_bridge_table_name()
        else:
            bridge_table_name = f"{group.temp_table_name}_bridge"

        # 获取该组的JOIN类型
        category = self._get_category_for_platform(group.platform)
        join_type = self.config.get_join_type(category, group.platform)

        sql_parts = []

        # 如果未启用全局桥接，为每个分组创建独立桥接表
        if not self.config.credit_bridge_enabled:
            primary_table = group.tables[0]
            # 获取主表的实际 join_key（如 report_no / reportno / pboc_bs61_073）
            primary_meta = self.metadata.get_table(primary_table)
            primary_join_key = primary_meta.join_key if primary_meta else group.join_key

            sql_parts.append(f"-- ===== 征信桥接表 =====")
            sql_parts.append(f"DROP TABLE IF EXISTS {bridge_table_name};")
            sql_parts.append(f"CREATE TABLE {bridge_table_name} AS")
            sql_parts.append(f"SELECT {sample_alias}.{sample_key}, {sample_alias}.{bridge_key}")
            sql_parts.append(f"FROM {sample_table} {sample_alias}")

            primary_subquery = self.build_credit_primary_subquery(
                primary_table, primary_join_key, sample_table, bridge_key
            )
            sql_parts.append(f"INNER JOIN (")
            sql_parts.append(self._indent(primary_subquery))
            sql_parts.append(f") t ON {sample_alias}.{bridge_key} = t.{primary_join_key}")
            sql_parts.append(";")
            sql_parts.append("")

        # 创建征信变量临时表：桥接表 LEFT JOIN 各征信表
        sql_parts.append(f"DROP TABLE IF EXISTS {group.temp_table_name};")
        sql_parts.append(f"CREATE TABLE {group.temp_table_name} AS")

        # SELECT字段（桥接表使用别名 bridge，避免与子查询别名 b 冲突）
        # 桥接表的主键是 ci_rpt_id（征信报告号），用于统一关联各征信子表
        select_parts = [f"bridge.{sample_key}",
                        "bridge.ci_rpt_id"]

        seen_vars = {sample_key, "ci_rpt_id"}
        alias_map = {}
        for idx, t in enumerate(group.tables, start=1):
            alias_map[t] = chr(ord('a') + idx - 1)

        for t in group.tables:
            alias = alias_map[t]
            for var in group.table_vars[t]:
                db_col = self._get_db_column_name(var)
                if var in seen_vars:
                    select_parts.append(f"{alias}.{db_col} AS {alias}_{var}")
                else:
                    if db_col != var:
                        select_parts.append(f"{alias}.{db_col} AS {var}")
                    else:
                        select_parts.append(f"{alias}.{var}")
                    seen_vars.add(var)

        sql_parts.append("SELECT")
        sql_parts.append(",\n".join([f"    {p}" for p in select_parts]))
        sql_parts.append(f"FROM {bridge_table_name} bridge")

        # JOIN各征信表（支持自定义JOIN条件）
        for t in group.tables:
            alias = alias_map[t]
            # 获取该表的实际 join_key（如 report_no / reportno / pboc_bs61_073）
            table_meta = self.metadata.get_table(t)
            actual_join_key = table_meta.join_key if table_meta else group.join_key

            # 征信变量通过桥接表过滤，使用桥接表的 ci_rpt_id 作为过滤源
            subquery = self.subquery.build_single_table_subquery(
                t, group.table_vars[t],
                actual_join_key, bridge_table_name, 'ci_rpt_id'
            )

            # 构建ON条件：桥接表.ci_rpt_id = 子查询.ci_rpt_id
            # 子查询中 join_key 已统一 AS 为 ci_rpt_id，ON 条件也使用 ci_rpt_id
            on_clause = self.subquery.build_on_clause(
                t, alias, 'bridge', 'ci_rpt_id', 'ci_rpt_id'
            )

            sql_parts.append(f"{join_type} (")
            sql_parts.append(self._indent(subquery))
            sql_parts.append(f") {alias} ON {on_clause}")

        sql_parts.append(";")
        return "\n".join(sql_parts)

    def build_credit_primary_subquery(self, table_name: str,
                                       join_key: str,
                                       sample_table: str,
                                       bridge_key: str) -> str:
        """构建征信主键表子查询（只取join_key，用于桥接）"""
        resolved_table_name = self.config.resolve_table_name(table_name)
        table_meta = self.metadata.get_table(table_name)
        partition_field = table_meta.partition_field if table_meta else "dt"
        category = table_meta.category if table_meta else ""
        platform = table_meta.platform if table_meta else ""

        # 获取分区控制策略配置
        partition_config = self.config.get_partition_config(table_name, category, platform)
        partition_strategy = partition_config.get('strategy', 'equality')
        partition_control_field = partition_config.get('partition_field', partition_field)

        # 根据分区策略生成分区条件
        if partition_strategy == 'range':
            min_partition = partition_config.get('min_partition')
            if min_partition:
                partition_condition = f"t.{partition_control_field} >= {min_partition}"
            else:
                partition_condition = f"t.{partition_control_field} = '${{biz_date}}'"
        else:
            partition_condition = f"t.{partition_control_field} = '${{biz_date}}'"

        return f"""SELECT DISTINCT t.{join_key}
FROM {resolved_table_name} t
WHERE {partition_condition}
  AND t.{join_key} IN (
      SELECT {bridge_key} FROM {sample_table}
  )"""

    def build_credit_bridge_table(self, sample_table: str,
                                   sample_key: str) -> Optional[str]:
        """
        构建全局征信桥接表SQL

        根据credit_primary_table配置生成桥接表：
        1. 关联样本表与征信主键表（支持MD5转换）
        2. 按时间窗口过滤（如90天内）
        3. 取最新一条征信报告（ROW_NUMBER = 1）
        """
        cfg = self.config.credit_primary_table
        if not cfg or not cfg.get('enabled', False):
            return None

        table_name = self.config.resolve_table_name(
            cfg.get('table_name', 'wdyy_mrs.t_pbci_summary_other')
        )
        primary_key = cfg.get('primary_key', 'ci_rpt_id')
        sample_link_key = cfg.get('sample_link_key', 'be_qry_cert_num')
        sample_bridge_key = cfg.get('sample_bridge_key', 'cert_no')
        partition_field = cfg.get('partition_field', 'part_id')
        time_field = cfg.get('time_field', 'rpt_tm')
        sample_time_field = cfg.get('sample_time_field', 'issue_time')
        time_window_days = cfg.get('time_window_days', 90)
        md5_transform = cfg.get('md5_transform', True)
        time_expr = cfg.get('time_expr', 'to_date(substr({field}, 1, 10))')
        sample_expr = cfg.get('sample_expr', 'to_date({field})')
        direction = cfg.get('direction', '<=')

        bridge_table_name = self.config.get_credit_bridge_table_name()

        # 构建JOIN条件（支持MD5转换）
        if md5_transform:
            join_condition = f"a.{sample_bridge_key} = md5(b.{sample_link_key})"
        else:
            join_condition = f"a.{sample_bridge_key} = b.{sample_link_key}"

        # 构建时间表达式
        table_time_expr = time_expr.format(field=f"b.{time_field}")
        sample_time_expr = sample_expr.format(field=f"a.{sample_time_field}")

        # 构建时间过滤条件
        time_filter = f"{table_time_expr} {direction} {sample_time_expr}"
        window_filter = f"DATEDIFF({sample_time_expr}, {table_time_expr}) <= {time_window_days}"

        sql = f"""-- ===== 征信桥接表（基于配置生成） =====
DROP TABLE IF EXISTS {bridge_table_name};
CREATE TABLE {bridge_table_name} AS
SELECT a.*
FROM (
    SELECT a.*
           ,b.{primary_key}
           ,ROW_NUMBER() OVER (PARTITION BY a.{sample_key} ORDER BY b.{time_field} DESC) AS rn
    FROM {sample_table} a
    JOIN {table_name} b
    ON {join_condition}
    WHERE {time_filter}
    AND {window_filter}
) a
WHERE rn = 1;"""

        return sql

    def _indent(self, sql: str, level: int = 1) -> str:
        """SQL缩进"""
        indent = self.INDENT * level
        return "\n".join([indent + line for line in sql.split("\n")])

    def _get_db_column_name(self, var_name: str) -> str:
        """获取变量的数据库实际列名"""
        var_meta = self.metadata.get_variable(var_name)
        if var_meta and var_meta.db_column_name and var_meta.db_column_name != var_name:
            return var_meta.db_column_name
        return var_name

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
