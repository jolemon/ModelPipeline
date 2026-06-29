"""
配置覆盖应用器

负责将外部配置（变量覆盖、表关联键覆盖、变量别名映射）
应用到 MetadataManager 的元数据上。
"""

from typing import Dict, Optional

from src.metadata.models import VariableMetadata, TableMetadata


class OverrideApplier:
    """
    配置覆盖应用器

    将配置文件中的覆盖项应用到元数据：
    - 变量覆盖：指定异常变量的来源表
    - 表关联键覆盖：覆盖各表的 join_key / partition_field
    - 变量别名映射：模型变量名 -> 数据库列名
    """

    def __init__(self, metadata_manager):
        """
        初始化覆盖应用器

        Args:
            metadata_manager: MetadataManager 实例
        """
        self._metadata = metadata_manager

    def apply_variable_overrides(self,
                                  overrides: Dict[str, Dict[str, str]],
                                  table_join_keys: Optional[Dict[str, Dict[str, str]]] = None) -> None:
        """应用变量覆盖配置到元数据

        variable_overrides 仅用于指定变量的来源表，
        join_key 和 partition_field 优先从 table_join_keys 获取，
        如未配置则使用元数据默认值或系统默认。

        Args:
            overrides: {var_name: {source_table: ...}}
            table_join_keys: {表名: {join_key: ..., partition_field: ...}}，可选
        """
        table_join_keys = table_join_keys or {}

        for var_name, cfg in overrides.items():
            source_table = cfg.get('source_table', '')

            # 优先从 table_join_keys 获取关联键和分区字段
            table_cfg = table_join_keys.get(source_table, {})
            join_key = table_cfg.get('join_key', 'apply_no')
            partition_field = table_cfg.get('partition_field', 'dt')

            var_meta = VariableMetadata(
                var_name=var_name,
                source_table=source_table,
                join_key=join_key,
                partition_field=partition_field,
                category='覆盖变量',
                platform='override'
            )
            self._metadata.variables[var_name] = var_meta

            # 从其他表中移除该变量，避免被识别为歧义变量
            for tbl_name, tbl_meta in list(self._metadata.tables.items()):
                if tbl_name != source_table and var_name in tbl_meta.variables:
                    tbl_meta.variables.remove(var_name)

            if source_table and source_table not in self._metadata.tables:
                table_meta = TableMetadata(
                    table_name=source_table,
                    join_key=join_key,
                    partition_field=partition_field,
                    category='覆盖变量',
                    platform='override',
                    variables=[var_name]
                )
                self._metadata.tables[source_table] = table_meta
            elif source_table and source_table in self._metadata.tables:
                if var_name not in self._metadata.tables[source_table].variables:
                    self._metadata.tables[source_table].variables.append(var_name)
                # 同步更新已有表的关联键（如果table_join_keys有配置）
                if source_table in table_join_keys:
                    self._metadata.tables[source_table].join_key = join_key
                    self._metadata.tables[source_table].partition_field = partition_field

    def apply_table_join_key_overrides(self,
                                        table_join_keys: Dict[str, Dict[str, str]]) -> None:
        """应用config.yaml中的表关联键覆盖配置

        覆盖metadata.yaml中各表的join_key和partition_field，
        同时同步更新该表下所有变量的关联键信息。

        Args:
            table_join_keys: {表名: {join_key: ..., partition_field: ...}}
        """
        for table_name, cfg in table_join_keys.items():
            new_join_key = cfg.get('join_key')
            new_partition = cfg.get('partition_field')

            # 更新表级别的关联键
            if table_name in self._metadata.tables:
                table_meta = self._metadata.tables[table_name]
                if new_join_key:
                    table_meta.join_key = new_join_key
                if new_partition:
                    table_meta.partition_field = new_partition

                # 同步更新该表下所有变量的关联键
                for var_name in table_meta.variables:
                    if var_name in self._metadata.variables:
                        var_meta = self._metadata.variables[var_name]
                        if new_join_key:
                            var_meta.join_key = new_join_key
                        if new_partition:
                            var_meta.partition_field = new_partition

                print(f"  [表关联键覆盖] {table_name}: "
                      f"join_key={table_meta.join_key}, partition={table_meta.partition_field}")

    def apply_variable_aliases(self, aliases: Dict[str, str]) -> None:
        """应用变量名别名映射到元数据

        当模型变量名与数据库实际列名不一致时，
        通过此配置更新 VariableMetadata 的 db_column_name 字段。
        例如：模型变量 'new_feature_v2' -> 数据库列 'new_feature_v2_2025'

        Args:
            aliases: {模型变量名: 数据库列名} 的映射字典
        """
        if not aliases:
            return

        applied_count = 0
        for var_name, db_column in aliases.items():
            if var_name in self._metadata.variables:
                self._metadata.variables[var_name].db_column_name = db_column
                applied_count += 1
                print(f"  [变量别名映射] {var_name} -> {db_column}")
            else:
                print(f"  [WARN] 变量别名映射未命中: {var_name} (未在元数据中找到)")

        print(f"[变量别名映射] 共应用 {applied_count}/{len(aliases)} 个映射")
