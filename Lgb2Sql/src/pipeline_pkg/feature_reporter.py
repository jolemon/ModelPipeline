"""
特征元数据报告模块

负责生成入模变量的元数据报告，包括：
- 变量匹配状态（正常/缺失/歧义/覆盖）
- 平台分布统计
- 异常变量详细报告
"""

from typing import List, Dict, Optional, Any

from metadata import MetadataManager
from src.core.config_loader import SQLConfig


class FeatureReporter:
    """入模变量元数据报告生成器"""

    def __init__(self, metadata: MetadataManager, config: SQLConfig):
        """初始化入模变量元数据报告生成器

        Args:
            metadata: 元数据管理器
            config: SQL配置对象
        """
        self.metadata = metadata
        self.config = config

    def generate_report(self, features: List[str],
                        resolved_ambiguous: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        生成变量元数据报告

        Args:
            features: 入模变量列表
            resolved_ambiguous: 歧义变量解析结果 {变量名: 选定的来源表名}，
                               由 JoinPlanner._resolve_ambiguous_variables() 生成

        Returns:
            报告字典，包含分类统计和详细元数据
        """
        feature_meta: Dict[str, Any] = {}
        overrides = self.config.variable_overrides

        normal_vars = []
        missing_vars = []
        ambiguous_vars = []
        override_vars = []

        # 先检测歧义变量
        ambiguous = self.metadata.find_ambiguous_variables(features)

        for var_name in features:
            # 优先级1: 检查是否有覆盖配置
            override = overrides.get(var_name)
            if override:
                override_vars.append(var_name)
                feature_meta[var_name] = {
                    'var_name': var_name,
                    'status': 'OVERRIDE',
                    'source_table': override.get('source_table', 'N/A'),
                    'join_key': override.get('join_key', 'N/A'),
                    'partition_field': override.get('partition_field', 'dt'),
                    'override_config': override
                }
                continue

            var_meta = self.metadata.get_variable(var_name)

            if var_meta:
                if var_name in ambiguous:
                    ambiguous_vars.append(var_name)

                    # 如果提供了歧义解析结果，使用解析后的表名及其元数据
                    resolved_table = resolved_ambiguous.get(var_name) if resolved_ambiguous else None
                    if resolved_table:
                        source_table = resolved_table
                        table_meta = self.metadata.get_table(resolved_table)
                        category = table_meta.category if table_meta else var_meta.category
                        platform = table_meta.platform if table_meta else var_meta.platform
                        join_key = table_meta.join_key if table_meta else var_meta.join_key
                        partition_field = table_meta.partition_field if table_meta else var_meta.partition_field
                    else:
                        source_table = var_meta.source_table or 'N/A'
                        category = var_meta.category
                        platform = var_meta.platform
                        join_key = var_meta.join_key
                        partition_field = var_meta.partition_field

                    feature_meta[var_name] = {
                        'var_name': var_name,
                        'status': 'AMBIGUOUS',
                        'source_table': source_table,
                        'matched_tables': ambiguous[var_name],
                        'var_desc': var_meta.var_desc or 'N/A',
                        'category': category or 'N/A',
                        'platform': platform or 'N/A',
                        'join_key': join_key or 'N/A',
                        'partition_field': partition_field or 'N/A',
                    }
                else:
                    normal_vars.append(var_name)
                    feature_meta[var_name] = {
                        'var_name': var_meta.var_name,
                        'status': 'OK',
                        'var_desc': var_meta.var_desc or 'N/A',
                        'source_table': var_meta.source_table or 'N/A',
                        'table_desc': var_meta.table_desc or 'N/A',
                        'category': var_meta.category or 'N/A',
                        'platform': var_meta.platform or 'N/A',
                        'join_key': var_meta.join_key or 'N/A',
                        'partition_field': var_meta.partition_field or 'N/A',
                    }
            else:
                missing_vars.append(var_name)
                feature_meta[var_name] = {
                    'var_name': var_name,
                    'status': 'NOT_FOUND',
                    'source_table': 'N/A',
                    'join_key': 'N/A',
                    'partition_field': 'N/A'
                }

        return {
            'feature_meta': feature_meta,
            'normal_vars': normal_vars,
            'missing_vars': missing_vars,
            'ambiguous_vars': ambiguous_vars,
            'override_vars': override_vars,
            'total': len(features)
        }
    

    def print_report(self, report: Dict[str, Any]) -> None:
        """打印变量元数据报告到控制台

        Args:
            report: generate_report生成的报告字典
        """
        feature_meta = report['feature_meta']
        normal_vars = report['normal_vars']
        missing_vars = report['missing_vars']
        ambiguous_vars = report['ambiguous_vars']
        override_vars = report['override_vars']
        total = report['total']

        print(f"\n共查询 {total} 个变量的元数据:\n")
        print(f"  正常命中:   {len(normal_vars)} / {total}")
        print(f"  未命中:     {len(missing_vars)} / {total}")
        print(f"  歧义变量:   {len(ambiguous_vars)} / {total}")
        if override_vars:
            print(f"  配置覆盖:   {len(override_vars)} / {total}")

        # 平台统计（包含正常变量和已解析的歧义变量）
        platform_stats: Dict[str, int] = {}
        for var_name in normal_vars + ambiguous_vars:
            platform = feature_meta[var_name].get('platform', 'unknown')
            platform_stats[platform] = platform_stats.get(platform, 0) + 1

        if platform_stats:
            print("\n[平台分布（命中元数据变量）]")
            for platform, count in sorted(platform_stats.items(), key=lambda x: -x[1]):
                print(f"  {platform:20s}: {count:3d} 个变量")

        # 详细异常报告
        if missing_vars:
            print(f"\n[未命中元数据的变量（{len(missing_vars)}个）]")
            print("  这些变量在元数据中找不到映射，可能原因：")
            print("    - 变量名拼写错误")
            print("    - 元数据尚未收录该变量")
            print("    - 可通过 variable_overrides 配置强制指定")
            for name in missing_vars:
                print(f"    [WARN] {name}")

        if ambiguous_vars:
            print(f"\n[歧义变量（同时匹配多张表）（{len(ambiguous_vars)}个）]")
            print("  这些变量在多个表中出现，已按平台规则自动解析来源表。")
            print("  建议通过 variable_overrides 配置明确指定来源表。")
            for var_name in ambiguous_vars:
                meta = feature_meta[var_name]
                print(f"    [WARN] {var_name}")
                print(f"      当前使用表: {meta['source_table']}")
                print(f"      匹配到的所有表:")
                for tbl in meta['matched_tables']:
                    marker = "  /:em_209:/" if tbl == meta['source_table'] else "      "
                    print(f"{marker} {tbl}")

        if override_vars:
            print(f"\n[配置覆盖的变量（{len(override_vars)}个）]")
            print("  这些变量通过 config.yaml 中的 variable_overrides 强制指定：")
            for var_name in override_vars:
                meta = feature_meta[var_name]
                ov = meta['override_config']
                print(f"    /:em_209:/ {var_name}")
                print(f"      来源表: {ov.get('source_table', 'N/A')}")
                print(f"      关联键: {ov.get('join_key', 'N/A')}")
                print(f"      分区字段: {ov.get('partition_field', 'dt')}")
