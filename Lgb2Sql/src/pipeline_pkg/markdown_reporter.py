"""
Markdown 报告生成模块

负责生成 LightGBM -> Hive SQL 任务流的 Markdown 格式报告，包括：
- 配置信息
- 入模变量列表
- 元数据匹配统计
- 关联计划摘要
- 生成的 SQL
- 警告汇总
"""

from typing import List, Dict, Optional, Any
from datetime import datetime

from src.core.config_loader import SQLConfig
from src.core.sql_builder import SQLBuilder
from src.pipeline_pkg.feature_reporter import FeatureReporter


class MarkdownReporter:
    """Markdown 格式任务流报告生成器"""

    def __init__(self, config: SQLConfig, sql_builder: SQLBuilder,
                 feature_reporter: FeatureReporter):
        """初始化 Markdown 报告生成器

        Args:
            config: SQL 配置对象
            sql_builder: SQL 构建器
            feature_reporter: 特征报告器
        """
        self.config = config
        self.sql_builder = sql_builder
        self.feature_reporter = feature_reporter

    def generate(self,
                 model_path: str,
                 result: Dict[str, Any],
                 sample_config: Optional[dict],
                 output_config: Optional[dict],
                 mode: str,
                 generate_score: bool) -> str:
        """生成 Markdown 格式的任务流报告

        Args:
            model_path: 模型文件路径
            result: 任务流结果字典（含 join_sql / score_sql / features / feature_metadata）
            sample_config: 样本表配置
            output_config: 输出表配置
            mode: SQL 生成模式
            generate_score: 是否生成了打分 SQL

        Returns:
            Markdown 格式报告字符串
        """
        lines = []
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 标题
        lines.append("# LightGBM -> Hive SQL 任务流报告\n")
        lines.append(f"**生成时间**: {now}  \n")
        lines.append(f"**模型路径**: `{model_path}`  \n")
        lines.append("---\n")

        # 1. 配置信息
        lines.append("## 1. 任务流配置信息\n")
        lines.append("| 配置项 | 值 |")
        lines.append("|--------|-----|")
        lines.append(f"| 工作编号 (work_no) | {self.config.work_no} |")
        lines.append(f"| 模型编号 (model_id) | {self.config.model_id} |")
        lines.append(f"| 日期格式 | {self.config.date_format} |")
        lines.append(f"| 当前日期 | {self.config.get_date_str()} |")
        lines.append(f"| 最大子查询关联数 | {self.config.max_subquery_join} |")
        lines.append(f"| 空值填充值 (COALESCE) | {self.config.coalesce_value} |")
        lines.append(f"| 分区字段 | {self.config.partition_field} |")
        lines.append(f"| 分区变量 | {self.config.partition_var} |")
        lines.append(f"| 变量总数 | {len(self.sql_builder.metadata.variables)} |")
        lines.append(f"| 表总数 | {len(self.sql_builder.metadata.tables)} |")
        lines.append("")

        # 2. 入模变量列表
        features = result.get('features', [])
        lines.append(f"## 2. 入模变量列表（共 {len(features)} 个）\n")
        lines.append("| 序号 | 变量名 |")
        lines.append("|------|--------|")
        for i, name in enumerate(features, 1):
            lines.append(f"| {i} | `{name}` |")
        lines.append("")

        # 3. 元数据信息
        lines.append("## 3. 入模变量元数据信息\n")
        meta = result.get('feature_metadata', {})

        normal_vars = [v for v, m in meta.items() if m.get('status') == 'OK']
        missing_vars = [v for v, m in meta.items() if m.get('status') == 'NOT_FOUND']
        ambiguous_vars = [v for v, m in meta.items() if m.get('status') == 'AMBIGUOUS']
        override_vars = [v for v, m in meta.items() if m.get('status') == 'OVERRIDE']

        lines.append("### 3.1 匹配统计\n")
        lines.append("| 状态 | 数量 |")
        lines.append("|------|------|")
        lines.append(f"| 正常命中 | {len(normal_vars)} |")
        lines.append(f"| 未命中 | {len(missing_vars)} |")
        lines.append(f"| 歧义变量 | {len(ambiguous_vars)} |")
        lines.append(f"| 配置覆盖 | {len(override_vars)} |")
        lines.append("")

        # 平台分布（包含正常变量和已解析的歧义变量）
        platform_stats = {}
        for var_name in normal_vars + ambiguous_vars:
            platform = meta[var_name].get('platform', 'unknown')
            platform_stats[platform] = platform_stats.get(platform, 0) + 1
        if platform_stats:
            lines.append("### 3.2 平台分布（命中元数据变量）\n")
            lines.append("| 平台 | 变量数 |")
            lines.append("|------|--------|")
            for platform, count in sorted(platform_stats.items(), key=lambda x: -x[1]):
                lines.append(f"| {platform} | {count} |")
            lines.append("")

        # 异常详情
        if missing_vars:
            lines.append("### 3.3 未命中元数据的变量\n")
            for name in missing_vars:
                lines.append(f"- `{name}`")
            lines.append("")

        if ambiguous_vars:
            lines.append("### 3.4 歧义变量（多表匹配）\n")
            for var_name in ambiguous_vars:
                m = meta[var_name]
                lines.append(f"#### `{var_name}`")
                lines.append(f"- **当前使用表**: {m.get('source_table', 'N/A')}")
                lines.append(f"- **匹配到的所有表**:")
                for tbl in m.get('matched_tables', []):
                    marker = "/:em_209:/" if tbl == m.get('source_table') else ""
                    lines.append(f"  - {marker} `{tbl}`")
                lines.append("")

        if override_vars:
            lines.append("### 3.5 配置覆盖的变量\n")
            for var_name in override_vars:
                m = meta[var_name]
                ov = m.get('override_config', {})
                lines.append(
                    f"- `{var_name}` -> 表: `{ov.get('source_table', 'N/A')}`, "
                    f"关联键: `{ov.get('join_key', 'N/A')}`, "
                    f"分区: `{ov.get('partition_field', 'dt')}`"
                )
            lines.append("")

        # 黑名单
        blacklisted = self.config.check_blacklist(features)
        if blacklisted:
            lines.append("### 3.6 [WARN] 黑名单告警\n")
            lines.append(f"发现 **{len(blacklisted)}** 个禁用变量：")
            for var in blacklisted:
                m = meta.get(var, {})
                lines.append(f"- `{var}` (来源表: {m.get('source_table', '未知')})")
            lines.append("")

        # 零重要度特征
        zero_imp = result.get('zero_importance_features', [])
        if zero_imp:
            lines.append("### 3.7 [INFO] 零重要度特征（已自动过滤）\n")
            lines.append(f"以下 **{len(zero_imp)}** 个变量特征重要度(Gain)为 **0**，不参与模型分数计算，已自动过滤：\n")
            for var in zero_imp:
                lines.append(f"- `{var}`")
            lines.append("\n> **说明**：这些变量在模型训练时未被任何树选中作为分裂节点，对模型输出无贡献。")
            lines.append("")

        # 4. 关联计划
        lines.append("## 4. 关联计划摘要\n")
        sc = sample_config or {'table_name': 'dwd_apply_info', 'key': 'apply_no'}
        plan = self.sql_builder.planner.plan(
            model_features=features,
            sample_table=sc.get('table_name', 'dwd_apply_info'),
            sample_key=sc.get('key', 'apply_no'),
            sample_fields=sc.get('fields', [sc.get('key', 'apply_no')])
        )
        lines.append(f"- **样本表**: `{plan.sample_table}`")
        lines.append(f"- **样本主键**: `{plan.sample_key}`")
        lines.append(f"- **CTE分组数**: {len(plan.groups)}")
        lines.append("")

        for i, group in enumerate(plan.groups, 1):
            lines.append(f"### 分组 {i}: `{group.group_id}`")
            lines.append(f"- **平台**: {group.platform} ({group.platform_en})")
            lines.append(f"- **关联键**: `{group.join_key}`")
            lines.append(f"- **表数量**: {len(group.tables)}")
            for table in group.tables:
                lines.append(f"  - `{table}`")
            lines.append(f"- **变量数**: {len(group.all_variables)}")
            if group.duplicate_vars:
                lines.append(f"- **重复变量**: {len(group.duplicate_vars)} 个")
                for var in group.duplicate_vars:
                    lines.append(f"  - `{var}`")
            lines.append("")

        # 5. 生成的 SQL
        lines.append("## 5. 生成的SQL\n")

        join_sql = result.get('join_sql', '')
        lines.append("### 5.1 JOIN SQL\n")
        lines.append("```sql")
        lines.append(join_sql)
        lines.append("```")
        lines.append("")

        score_sql = result.get('score_sql')
        if generate_score and score_sql:
            lines.append("### 5.2 打分SQL\n")
            lines.append("```sql")
            lines.append(score_sql)
            lines.append("```")
            lines.append("")

        # 6. 警告汇总
        warnings = []
        if missing_vars:
            warnings.append(f"未命中元数据变量: {len(missing_vars)} 个")
        if ambiguous_vars:
            warnings.append(f"歧义变量（多表匹配）: {len(ambiguous_vars)} 个")
        if blacklisted:
            warnings.append(f"黑名单禁用变量: {len(blacklisted)} 个")

        if warnings:
            lines.append("## 6. [WARN] 警告汇总\n")
            for w in warnings:
                lines.append(f"- {w}")
            lines.append("")

        lines.append("---\n")
        lines.append("*报告由 LgbToSqlPipeline 自动生成*\n")

        return "\n".join(lines)
