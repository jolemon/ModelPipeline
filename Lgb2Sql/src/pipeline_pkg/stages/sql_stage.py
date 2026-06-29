"""
SQL生成 Stage

职责：根据关联逻辑生成 JOIN SQL，打印关联计划摘要
"""

from typing import Dict, List, Optional

from src.core.models import OutputConfig


class SQLGenerationStage:
    """SQL生成 Stage：生成 JOIN SQL"""

    def execute(self, ctx,
                features: Optional[List[str]] = None,
                sample_config: Optional[dict] = None,
                output_config: Optional[dict] = None,
                mode: str = 'temp_table') -> str:
        """根据关联逻辑进行表关联，输出SQL语句

        Args:
            ctx: PipelineContext
            features: 入模变量列表
            sample_config: 样本表配置
            output_config: 输出表配置
            mode: SQL生成模式，'cte'或'temp_table'

        Returns:
            生成的Hive SQL字符串
        """
        features = features or ctx.features
        if not features:
            from src.pipeline_pkg.pipeline_core import PipelineError
            raise PipelineError("尚未提取入模变量，请先调用extract_features()")

        sample_config = sample_config or {
            'table_name': 'dwd_apply_info',
            'key': 'apply_no',
            'fields': ['apply_no']
        }

        output_config = output_config or {
            'output_table': 'model_score_input',
            'output_db': '',
            'coalesce_value': ctx.config.coalesce_value
        }

        print("\n" + "=" * 70)
        print(f" 步骤4: 生成SQL语句 (模式: {mode}) ")
        print("=" * 70)

        oc = OutputConfig(
            output_table=output_config.get('output_table', 'model_score_input'),
            output_db=output_config.get('output_db', ''),
            coalesce_value=output_config.get('coalesce_value', ctx.config.coalesce_value)
        )

        if mode == 'cte':
            sql = ctx.sql_builder.build_cte_sql(features, sample_config, oc)
        else:
            sql = ctx.sql_builder.build_temp_table_sql(features, sample_config, oc)

        # 打印执行计划摘要
        plan = ctx.sql_builder.planner.plan(
            model_features=features,
            sample_table=sample_config['table_name'],
            sample_key=sample_config.get('key', 'apply_no'),
            sample_fields=sample_config.get('fields', [sample_config.get('key', 'apply_no')])
        )

        print(f"\n[关联计划摘要]")
        print(f"  样本表:     {plan.sample_table}")
        print(f"  样本主键:   {plan.sample_key}")
        print(f"  CTE分组数:  {len(plan.groups)}")

        for i, group in enumerate(plan.groups, 1):
            print(f"\n  分组 {i}: {group.group_id}")
            print(f"    平台:     {group.platform} ({group.platform_en})")
            print(f"    关联键:   {group.join_key}")
            print(f"    表数量:   {len(group.tables)}")
            for table in group.tables:
                print(f"      - {table}")
            print(f"    变量数:   {len(group.all_variables)}")
            if group.duplicate_vars:
                print(f"    重复变量: {len(group.duplicate_vars)} 个")

        print(f"\n/:em_209:/ SQL生成完成，总长度: {len(sql)} 字符")

        ctx.join_sql = sql
        ctx.join_plan = plan
        return sql
