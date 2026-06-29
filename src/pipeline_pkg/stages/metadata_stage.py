"""
元数据报告 Stage

职责：查询入模变量的元数据信息，生成报告，检查黑名单
"""

from typing import Dict, List, Optional, Any


class MetadataReportStage:
    """元数据报告 Stage：查询变量元数据，输出报告"""

    def execute(self, ctx, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """输出入模变量的元数据信息

        Args:
            ctx: PipelineContext
            features: 变量列表，若为None则使用已加载的特征

        Returns:
            变量元数据字典
        """
        features = features or ctx.features
        if not features:
            from src.pipeline_pkg.pipeline_core import PipelineError
            raise PipelineError("尚未提取入模变量，请先调用extract_features()")

        print("\n" + "=" * 70)
        print(" 步骤3: 入模变量元数据信息 ")
        print("=" * 70)

        # 通过 JoinPlanner 解析歧义变量，确保报告中的 source_table 与 SQL 实际生成一致
        resolved_ambiguous = ctx.sql_builder.planner._resolve_ambiguous_variables(features)
        if resolved_ambiguous:
            print(f"\n[歧义变量解析] 共 {len(resolved_ambiguous)} 个歧义变量已按平台规则解析:")
            for var_name, table_name in sorted(resolved_ambiguous.items()):
                print(f"  - {var_name} -> {table_name}")

        report = ctx.feature_reporter.generate_report(features, resolved_ambiguous=resolved_ambiguous)
        ctx.feature_meta = report['feature_meta']
        ctx.feature_reporter.print_report(report)

        # 检查黑名单命中情况
        blacklisted = ctx.config.check_blacklist(features)
        if blacklisted:
            print("\n" + "!" * 70)
            print(f" [ALERT] 黑名单告警: 发现 {len(blacklisted)} 个禁用变量")
            print("!" * 70)
            for i, var in enumerate(blacklisted, 1):
                meta = ctx.feature_meta.get(var, {})
                source_table = meta.get('source_table', '未知')
                print(f"  {i:3d}. {var:<40s} (来源表: {source_table})")
            print("!" * 70)
            print("  [WARN] 提示: 上述变量已列入禁用黑名单，请确认是否合规使用")
            print("!" * 70)

        return ctx.feature_meta
