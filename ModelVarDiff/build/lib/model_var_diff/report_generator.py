import os

from .analyzer import (OverviewStats, MatchStats, VariableMatchStats,
                       DrillUpRow, VariableAnalysis, AnomalyGroup)
from .config_loader import ConfigLoader, Config


class ReportGenerator:
    def __init__(self, output_dir: str, config: Config):
        self.output_dir = output_dir
        self.config = config

    def generate(self,
                 overview: OverviewStats,
                 score_stats: MatchStats,
                 var_stats: list[VariableMatchStats],
                 drill_up_multi: list[DrillUpRow],
                 var_analyses: list[VariableAnalysis] = ()):
        lines = []
        lines.append("# 模型变量对比报告")
        lines.append("")

        self._write_overview(lines, overview)
        self._write_score(lines, score_stats)
        self._write_variables_combined(lines, var_stats, overview)
        self._write_drill_up(lines, drill_up_multi)
        self._write_per_variable_analysis(lines, var_analyses)
        self._write_appendix(lines)

        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, "report.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path

    # ── Section 1 ────────────────────────────────────────────────

    def _write_overview(self, lines: list[str], o: OverviewStats):
        lines.append("## 1. 输入数据概况")
        lines.append("")
        lines.append(f"| 数据来源 | 行数 | 字段数 |")
        lines.append(f"|----------|------|--------|")
        lines.append(f"| 线上     | {o.online_rows} | {o.online_cols} |")
        lines.append(f"| 线下     | {o.offline_rows} | {o.offline_cols} |")
        lines.append(f"| 合并后 (inner join) | {o.merged_rows} | - |")
        lines.append("")

    # ── Section 2 ────────────────────────────────────────────────

    def _write_score(self, lines: list[str], s: MatchStats):
        lines.append("## 2. 分数校验结果")
        lines.append("")
        lines.append(f"- **匹配数量**: {s.match_count}/{s.total}")
        lines.append(f"- **匹配率**: {s.match_rate:.2%}")
        lines.append("")

    # ── Section 3 ────────────────────────────────────────────────

    def _write_variables_combined(self, lines: list[str], stats: list[VariableMatchStats],
                                   overview: OverviewStats):
        lines.append("## 3. 变量校验结果")
        lines.append("")
        lines.append(f"| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |")
        lines.append(f"|------|------------|------------|------------|--------|------|--------|")
        for v in stats:
            online_miss = overview.online_missing.get(v.name, 0)
            offline_miss = overview.offline_missing.get(v.name, 0)
            lines.append(
                f"| {v.name} | {v.data_source} "
                f"| {online_miss:.2%} | {offline_miss:.2%} "
                f"| {v.match_count} | {v.total} | {v.match_rate:.2%} |"
            )
        lines.append("")

    # ── Section 4 ────────────────────────────────────────────────

    def _write_drill_up(self, lines: list[str], drill_up_multi: list[DrillUpRow]):
        lines.append("## 4. 上钻分析（按数据源）")
        lines.append("")
        lines.append("按匹配严格程度，依次展示 5 个维度的匹配率：")
        lines.append("")
        lines.append("- **严格匹配**：该数据源下所有变量均匹配的行占比")
        lines.append("- **75% 匹配**：至少 75% 变量匹配的行占比")
        lines.append("- **50% 匹配**：至少 50% 变量匹配的行占比")
        lines.append("- **25% 匹配**：至少 25% 变量匹配的行占比")
        lines.append("- **宽松匹配**：任一变量匹配的行占比")
        lines.append("")

        lines.append(f"| 数据源 | 变量数 | 严格匹配 | 75%匹配 | 50%匹配 | 25%匹配 | 宽松匹配 |")
        lines.append(f"|--------|--------|----------|---------|---------|---------|----------|")
        for r in drill_up_multi:
            lines.append(
                f"| {r.data_source} | {r.var_count} "
                f"| {r.strict:.2%} | {r.match_75:.2%} | {r.match_50:.2%} "
                f"| {r.match_25:.2%} | {r.loose:.2%} |"
            )
        lines.append("")

    # ── Section 5 ────────────────────────────────────────────────

    def _write_per_variable_analysis(self, lines: list[str],
                                      var_analyses: list[VariableAnalysis]):
        if not var_analyses:
            return

        lines.append("## 5. 单变量分析")
        lines.append("")
        lines.append("以下按匹配率从低到高，逐个分析所有未严格匹配（匹配率 < 100%）的变量。")
        lines.append("")

        for va in var_analyses:
            lines.append(f"### {va.name}")
            lines.append("")

            # 5.1 Basic info table
            lines.append(f"| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |")
            lines.append(f"|------|------------|------------|------------|--------|------|--------|")
            lines.append(
                f"| {va.name} | {va.data_source} "
                f"| {va.online_missing_rate:.2%} | {va.offline_missing_rate:.2%} "
                f"| {va.match_count} | {va.total} | {va.match_rate:.2%} |"
            )
            lines.append("")

            # 5.2 Null-status breakdown
            lines.append("**按空值维度统计：**")
            lines.append("")
            lines.append(f"| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |")
            lines.append(f"|--------------|--------------|------|------|------------------------------|")
            for g in va.anomaly_groups:
                top_str = ", ".join(f"`{o}`/`{f}`" for o, f, _ in g.top_pairs) if g.top_pairs else "-"
                lines.append(
                    f"| {g.label} | {g.count} | {g.pct:.2%} | {top_str} |"
                )
            lines.append("")

            # 5.3 SQL code
            self._write_sql(lines, va)

            lines.append("---")
            lines.append("")

    def _write_sql(self, lines: list[str], va: VariableAnalysis):
        user_key = ConfigLoader.get_user_key(self.config)
        etldt = ConfigLoader.get_etldt(self.config)
        sample_date = ConfigLoader.get_sample_date(self.config)
        table_name = ConfigLoader.get_table_name(self.config, va.data_source)

        for g in va.anomaly_groups:
            samples = va.sql_samples.get(g.label, [])
            if not samples:
                continue
            pk_vals = [s[self.config.primary_keys[0]] for s in samples]
            pk_list = ",\n\t".join(f"'{v}'" for v in pk_vals)

            lines.append(f"```sql")
            lines.append(f"-- {va.name}")
            lines.append(f"-- {g.label}的{samples.__len__()}条样例")
            lines.append(f"SELECT {user_key} AS cert_no")
            lines.append(f"     , {etldt} AS etldt")
            lines.append(f"     , {va.name}")
            lines.append(f"     , datediff(To_date('{sample_date}'), To_date({etldt})) AS days_diff")
            lines.append(f"FROM {table_name}")
            lines.append(f"WHERE {user_key} IN (")
            lines.append(f"\t{pk_list}")
            lines.append(f")")
            lines.append(f"ORDER BY {user_key}, {etldt}")
            lines.append(f";")
            lines.append(f"```")
            lines.append("")

    # ── Appendix ─────────────────────────────────────────────────

    def _write_appendix(self, lines: list[str]):
        # Look in package dir first, then project root
        for base in [os.path.dirname(__file__),
                     os.path.join(os.path.dirname(__file__), "..")]:
            rules_path = os.path.join(base, "VALIDATION_RULES.md")
            if os.path.exists(rules_path):
                with open(rules_path, "r", encoding="utf-8") as f:
                    lines.append("")
                    lines.append(f.read().rstrip())
                    lines.append("")
                return
