"""
CSV → YAML 元数据转换器

将特征映射表（CSV）转换为 metadata.yaml 格式，
供 MetadataManager 加载使用。
"""

import csv
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Any

from shared.classifier import classify_category, classify_platform, classify_fallback
from src.metadata.key_inference import infer_join_keys, is_likely_key_field


def convert_csv_to_yaml(csv_path: str, yaml_path: str) -> dict:
    """
    将特征映射CSV转换为metadata.yaml

    Args:
        csv_path: 输入CSV文件路径（制表符分隔）
        yaml_path: 输出YAML文件路径

    Returns:
        转换后的YAML数据字典
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV文件不存在: {csv_path}")

    # 读取所有行
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        rows = list(reader)

    print(f"[INFO] 读取CSV完成，总行数: {len(rows)}")

    # ========== 第一阶段：收集所有变量和表信息 ==========
    var_to_tables: Dict[str, set] = defaultdict(set)
    table_to_rows: Dict[str, list] = defaultdict(list)

    for row in rows:
        var_name = row.get('字段名', '').strip().lower()
        # 新格式：库名 + 表名 组合为来源表
        db_name = row.get('库名', '').strip()
        tbl_name = row.get('表名', '').strip()
        old_source = row.get('来源表', '').strip()
        # 优先使用新格式的 库名.表名，否则回退到旧格式的来源表
        if db_name and tbl_name:
            source_table = f"{db_name}.{tbl_name}"
        else:
            source_table = old_source
        if not var_name or not source_table:
            continue

        var_to_tables[var_name].add(source_table)
        table_to_rows[source_table].append(row)

    # 检测重复字段（出现在多个表中的字段）
    duplicate_vars = {
        var: sorted(list(tables))
        for var, tables in var_to_tables.items()
        if len(tables) > 1
    }

    print(f"[INFO] 去重前变量数: {len(var_to_tables)}")
    print(f"[INFO] 跨表重复字段数: {len(duplicate_vars)}")

    # ========== 第二阶段：构建变量列表 ==========
    variables = []
    tables_dict = {}
    seen_combinations = set()

    for row in rows:
        var_name = row.get('字段名', '').strip().lower()
        var_desc = row.get('字段含义', '').strip()
        # 新格式：库名 + 表名 组合为来源表
        db_name = row.get('库名', '').strip()
        tbl_name = row.get('表名', '').strip()
        old_source = row.get('来源表', '').strip()
        if db_name and tbl_name:
            source_table = f"{db_name}.{tbl_name}"
        else:
            source_table = old_source
        table_desc = row.get('表描述', '').strip()

        if not var_name or not source_table:
            continue

        combo = (var_name, source_table)
        if combo in seen_combinations:
            continue
        seen_combinations.add(combo)

        # 分类
        category = classify_category(source_table)
        platform = classify_platform(source_table)
        if not category:
            category = classify_fallback(source_table, platform)

        # 推断主键
        join_key, join_key_candidates, partition_field = infer_join_keys(source_table, category)

        is_duplicate = var_name in duplicate_vars
        likely_key = is_likely_key_field(var_name)

        var_record = {
            'var_name': var_name,
            'var_desc': var_desc,
            'source_table': source_table,
            'table_desc': table_desc,
            'category': category,
            'platform': platform,
            'join_key': join_key,
            'join_key_candidates': join_key_candidates,
            'partition_field': partition_field,
            'is_duplicate': is_duplicate,
            'is_likely_key': likely_key
        }
        variables.append(var_record)

        # 构建表信息
        if source_table not in tables_dict:
            tables_dict[source_table] = {
                'table_desc': table_desc,
                'category': category,
                'platform': platform,
                'join_key': join_key,
                'join_key_candidates': join_key_candidates,
                'partition_field': partition_field,
                'variables': []
            }
        tables_dict[source_table]['variables'].append(var_name)

    # ========== 第三阶段：构建YAML结构 ==========
    category_dist = dict(Counter(v['category'] for v in variables).most_common())
    platform_dist = dict(Counter(v['platform'] for v in variables).most_common())

    yaml_data = {
        'metadata_info': {
            'source': str(csv_path),
            'total_variables': len(variables),
            'total_tables': len(tables_dict),
            'category_distribution': category_dist,
            'platform_distribution': platform_dist,
            'duplicate_variables': {
                'count': len(duplicate_vars),
                'likely_key_count': sum(1 for v in duplicate_vars if is_likely_key_field(v)),
                'details': [
                    {
                        'var_name': var,
                        'appears_in_count': len(tables),
                        'appears_in_tables': tables,
                        'is_likely_key': is_likely_key_field(var)
                    }
                    for var, tables in sorted(duplicate_vars.items(), key=lambda x: (-len(x[1]), x[0]))
                ]
            }
        },
        'variables': variables,
        'tables': [
            {
                'table_name': name,
                'table_desc': info['table_desc'],
                'category': info['category'],
                'platform': info['platform'],
                'join_key': info['join_key'],
                'join_key_candidates': info['join_key_candidates'],
                'partition_field': info['partition_field'],
                'variable_count': len(set(info['variables'])),
                'variables': sorted(list(set(info['variables'])))
            }
            for name, info in sorted(tables_dict.items())
        ]
    }

    # ========== 第四阶段：保存YAML ==========
    import yaml

    output_path = Path(yaml_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(
            yaml_data,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            indent=2
        )

    # ========== 输出统计报告 ==========
    _print_summary(variables, tables_dict, duplicate_vars, category_dist, platform_dist, yaml_path)

    return yaml_data


def _print_summary(variables, tables_dict, duplicate_vars, category_dist, platform_dist, yaml_path):
    """打印CSV到YAML转换的统计报告

    Args:
        variables: 变量记录列表
        tables_dict: 表信息字典
        duplicate_vars: 跨表重复变量字典 {变量名: [表名列表]}
        category_dist: 分类分布统计
        platform_dist: 平台分布统计
        yaml_path: 输出YAML文件路径
    """
    print("\n" + "=" * 70)
    print("✓ 转换完成!")
    print(f"  变量总数: {len(variables)}")
    print(f"  表总数: {len(tables_dict)}")
    print(f"  跨表重复字段数: {len(duplicate_vars)}")
    print(f"  其中疑似主键/通用字段: {sum(1 for v in duplicate_vars if is_likely_key_field(v))}")
    print(f"  输出文件: {yaml_path}")

    print("\n=== 分类(Category)分布 ===")
    for cat, cnt in category_dist.items():
        pct = cnt / len(variables) * 100
        print(f"  {cat:12s}: {cnt:5d} ({pct:5.1f}%)")

    print("\n=== 平台(Platform)分布 ===")
    for plat, cnt in platform_dist.items():
        pct = cnt / len(variables) * 100
        print(f"  {plat:20s}: {cnt:5d} ({pct:5.1f}%)")

    print("\n=== 重复字段TOP30（按出现表数排序）===")
    dup_details = sorted(duplicate_vars.items(), key=lambda x: (-len(x[1]), x[0]))
    for var, tables in dup_details[:30]:
        flag = "[主键/通用]" if is_likely_key_field(var) else "[业务变量?]"
        print(f"  {var:30s}: 出现在 {len(tables):2d} 个表 {flag}")

    # 单独列出疑似业务变量的重复字段
    biz_duplicates = [(var, tables) for var, tables in dup_details if not is_likely_key_field(var)]
    if biz_duplicates:
        print(f"\n=== 疑似业务变量的重复字段（共{len(biz_duplicates)}个，建议人工review）===")
        for var, tables in biz_duplicates[:20]:
            print(f"  {var:30s}: 出现在 {len(tables):2d} 个表 -> {tables}")

    print("=" * 70)
