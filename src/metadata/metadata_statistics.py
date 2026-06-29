"""
元数据统计报告器

提供元数据的多维度统计分析和可视化报告输出。
独立于 MetadataManager，专注于"统计"职责。
"""

import json
from typing import Dict, Any


class MetadataStatistics:
    """
    元数据统计报告器

    基于 MetadataManager 的数据，提供：
    - 总体概览（变量/表总数）
    - 分类/平台分布统计
    - 表维度详情
    - 变量完整性分析
    - JOIN键/分区字段分布
    - 特殊变量检测（重复、疑似主键）
    """

    def __init__(self, metadata_manager):
        """
        初始化统计报告器

        Args:
            metadata_manager: MetadataManager 实例
        """
        self._metadata = metadata_manager

    def get_statistics(self) -> Dict[str, Any]:
        """获取当前元数据的详细统计信息

        Returns:
            包含多维统计信息的字典
        """
        stats: Dict[str, Any] = {}

        # 1. 总体概览
        stats['overview'] = {
            'total_variables': len(self._metadata.variables),
            'total_tables': len(self._metadata.tables),
        }

        # 2. 变量分类统计 (category)
        category_stats: Dict[str, int] = {}
        for var in self._metadata.variables.values():
            cat = var.category or '_未分类_'
            category_stats[cat] = category_stats.get(cat, 0) + 1
        stats['category_distribution'] = dict(
            sorted(category_stats.items(), key=lambda x: -x[1])
        )

        # 3. 平台分布统计 (platform)
        platform_stats: Dict[str, int] = {}
        for var in self._metadata.variables.values():
            plat = var.platform or '_未指定_'
            platform_stats[plat] = platform_stats.get(plat, 0) + 1
        stats['platform_distribution'] = dict(
            sorted(platform_stats.items(), key=lambda x: -x[1])
        )

        # 4. 表维度统计
        table_stats = []
        for tbl_name, tbl in sorted(self._metadata.tables.items()):
            table_stats.append({
                'table_name': tbl_name,
                'variable_count': len(tbl.variables),
                'join_key': tbl.join_key or 'N/A',
                'partition_field': tbl.partition_field or 'N/A',
                'category': tbl.category or 'N/A',
                'platform': tbl.platform or 'N/A',
            })
        stats['table_details'] = table_stats

        # 5. 变量完整性统计
        total = len(self._metadata.variables)
        has_source_table = sum(1 for v in self._metadata.variables.values() if v.source_table)
        has_join_key = sum(1 for v in self._metadata.variables.values() if v.join_key)
        has_partition = sum(1 for v in self._metadata.variables.values() if v.partition_field)
        has_category = sum(1 for v in self._metadata.variables.values() if v.category)
        has_platform = sum(1 for v in self._metadata.variables.values() if v.platform)
        has_desc = sum(1 for v in self._metadata.variables.values() if v.var_desc)

        stats['completeness'] = {
            'total': total,
            'has_source_table': has_source_table,
            'has_join_key': has_join_key,
            'has_partition_field': has_partition,
            'has_category': has_category,
            'has_platform': has_platform,
            'has_description': has_desc,
            'missing_source_table': total - has_source_table,
            'missing_join_key': total - has_join_key,
            'missing_partition_field': total - has_partition,
        }

        # 6. 特殊变量统计
        duplicate_vars = [
            v for v in self._metadata.variables.values() if v.is_duplicate
        ]
        key_vars = [
            v for v in self._metadata.variables.values() if v.is_likely_key
        ]
        stats['special_variables'] = {
            'duplicate_count': len(duplicate_vars),
            'duplicate_names': [v.var_name for v in duplicate_vars],
            'likely_key_count': len(key_vars),
            'likely_key_names': [v.var_name for v in key_vars],
        }

        # 7. JOIN键分布
        join_key_stats: Dict[str, int] = {}
        for var in self._metadata.variables.values():
            if var.join_key:
                join_key_stats[var.join_key] = join_key_stats.get(var.join_key, 0) + 1
        stats['join_key_distribution'] = dict(
            sorted(join_key_stats.items(), key=lambda x: -x[1])
        )

        # 8. 分区字段分布
        partition_stats: Dict[str, int] = {}
        for var in self._metadata.variables.values():
            if var.partition_field:
                partition_stats[var.partition_field] = partition_stats.get(var.partition_field, 0) + 1
        stats['partition_field_distribution'] = dict(
            sorted(partition_stats.items(), key=lambda x: -x[1])
        )

        # 9. 变量来源表覆盖情况
        table_coverage: Dict[str, int] = {}
        for var in self._metadata.variables.values():
            tbl = var.source_table or '_未知_'
            table_coverage[tbl] = table_coverage.get(tbl, 0) + 1
        stats['source_table_distribution'] = dict(
            sorted(table_coverage.items(), key=lambda x: -x[1])
        )

        return stats

    def print_statistics(self) -> Dict[str, Any]:
        """打印元数据统计报告到控制台

        Returns:
            统计信息字典
        """
        stats = self.get_statistics()

        print("\n" + "=" * 70)
        print(" 元数据统计报告 ")
        print("=" * 70)

        # 总体概览
        overview = stats['overview']
        print(f"\n【总体概览】")
        print(f"  变量总数:   {overview['total_variables']:>6}")
        print(f"  表总数:     {overview['total_tables']:>6}")

        # 分类分布
        cat_dist = stats['category_distribution']
        if cat_dist:
            print(f"\n【变量分类分布】")
            for cat, count in list(cat_dist.items())[:10]:
                print(f"  {cat:20s}: {count:>5} 个")
            if len(cat_dist) > 10:
                print(f"  ... 及其他 {len(cat_dist) - 10} 个分类")

        # 平台分布
        plat_dist = stats['platform_distribution']
        if plat_dist:
            print(f"\n【平台分布】")
            for plat, count in list(plat_dist.items())[:10]:
                print(f"  {plat:20s}: {count:>5} 个")
            if len(plat_dist) > 10:
                print(f"  ... 及其他 {len(plat_dist) - 10} 个平台")

        # 表维度详情
        tbl_details = stats['table_details']
        if tbl_details:
            print(f"\n【表维度详情（共 {len(tbl_details)} 张）】")
            print(f"  {'表名':<30s} {'变量数':>6s} {'关联键':<12s} {'分区字段':<10s}")
            print("  " + "-" * 64)
            for t in tbl_details[:15]:
                print(f"  {t['table_name']:<30s} {t['variable_count']:>6d} "
                      f"{t['join_key']:<12s} {t['partition_field']:<10s}")
            if len(tbl_details) > 15:
                print(f"  ... 及其他 {len(tbl_details) - 15} 张表")

        # 完整性统计
        comp = stats['completeness']
        print(f"\n【变量元数据完整性】")
        print(f"  {'字段':<20s} {'已填写':>8s} {'缺失':>8s} {'完整率':>8s}")
        print("  " + "-" * 50)
        for field, has_field, miss_field in [
            ('来源表', comp['has_source_table'], comp['missing_source_table']),
            ('关联键', comp['has_join_key'], comp['missing_join_key']),
            ('分区字段', comp['has_partition_field'], comp['missing_partition_field']),
            ('分类', comp['has_category'], comp['total'] - comp['has_category']),
            ('平台', comp['has_platform'], comp['total'] - comp['has_platform']),
            ('描述', comp['has_description'], comp['total'] - comp['has_description']),
        ]:
            rate = has_field / comp['total'] * 100 if comp['total'] > 0 else 0
            print(f"  {field:<20s} {has_field:>8d} {miss_field:>8d} {rate:>7.1f}%")

        # JOIN键分布
        join_dist = stats['join_key_distribution']
        if join_dist:
            print(f"\n【JOIN键分布】")
            for key, count in list(join_dist.items())[:8]:
                print(f"  {key:20s}: {count:>5} 个变量")

        # 分区字段分布
        part_dist = stats['partition_field_distribution']
        if part_dist:
            print(f"\n【分区字段分布】")
            for field, count in list(part_dist.items())[:8]:
                print(f"  {field:20s}: {count:>5} 个变量")

        # 特殊变量
        special = stats['special_variables']
        if special['duplicate_count'] > 0:
            print(f"\n【跨表重复变量】{special['duplicate_count']} 个")
            for name in special['duplicate_names'][:10]:
                print(f"  ! {name}")
        if special['likely_key_count'] > 0:
            print(f"\n【疑似主键/通用字段】{special['likely_key_count']} 个")
            for name in special['likely_key_names'][:10]:
                print(f"  i {name}")

        print("=" * 70)
        return stats

    def get_statistics_json(self) -> str:
        """将统计信息导出为JSON字符串

        Returns:
            JSON格式的统计信息
        """
        return json.dumps(self.get_statistics(), ensure_ascii=False, indent=2)
