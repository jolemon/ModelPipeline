#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL 验证工具 - 生成数据校验SQL

用于验证自动化生成的SQL执行结果是否正确。
生成一系列Hive SQL语句，在目标库执行后可检查：
1. 样本量一致性
2. 变量缺失率
3. 数据波动
4. 主键唯一性
5. 评分分布

使用方式:
    from tools.sql_validator import SqlValidator
    validator = SqlValidator(output_table, sample_table, variables, date_field)
    sqls = validator.generate_all_validations()
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """验证SQL结果容器"""
    category: str           # 验证类别
    description: str        # 验证说明
    sql: str               # 可执行的Hive SQL
    metrics: List[str] = field(default_factory=list)  # 输出指标列名
    threshold_hint: str = ""  # 阈值建议


class SqlValidator:
    """
    SQL验证器 - 生成数据校验SQL

    Args:
        output_table: 输出表名（如 tmp_01011939_20260429_MYJBV4_ZY_var_output）
        sample_table: 样本表名（如 tmp_01011939_20260429_MYJBV4_ZY_sample）
        variables: 入模变量列表
        date_field: 日期/分区字段名（如 dt, part_id, data_dt）
        score_field: 评分字段名（默认 score_card）
        keep_columns: 保留列（主键等，默认 ['apply_no']）
    """

    def __init__(self,
                 output_table: str,
                 sample_table: str,
                 variables: List[str],
                 date_field: str = 'dt',
                 score_field: str = 'score_card',
                 keep_columns: Optional[List[str]] = None):
        """初始化SQL验证器。

        Args:
            output_table: 输出表名（如 tmp_01011939_20260429_MYJBV4_ZY_var_output）
            sample_table: 样本表名（如 tmp_01011939_20260429_MYJBV4_ZY_sample）
            variables: 入模变量列表
            date_field: 日期/分区字段名（如 dt, part_id, data_dt）
            score_field: 评分字段名（默认 score_card）
            keep_columns: 保留列（主键等，默认 ['apply_no']）
        """
        self.output_table = output_table
        self.sample_table = sample_table
        self.variables = variables
        self.date_field = date_field
        self.score_field = score_field
        self.keep_columns = keep_columns or ['apply_no']
        self.primary_key = keep_columns[0] if keep_columns else 'apply_no'

    # ==================== 1. 样本量一致性校验 ====================

    def generate_sample_count_check(self) -> ValidationResult:
        """
        按月统计：输出表样本数量 vs 样本表对比
        检查输出表记录数是否与样本表一致（或差异在合理范围内）
        """
        sql = f"""-- 1. 样本量一致性校验
-- 对比输出表与样本表各月记录数，差异应接近0

WITH sample_counts AS (
    SELECT
        CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT) AS month,
        COUNT(1) AS sample_cnt
    FROM {self.sample_table}
    GROUP BY CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT)
),
output_counts AS (
    SELECT
        CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT) AS month,
        COUNT(1) AS output_cnt
    FROM {self.output_table}
    GROUP BY CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT)
)
SELECT
    COALESCE(s.month, o.month) AS month,
    s.sample_cnt,
    o.output_cnt,
    COALESCE(o.output_cnt, 0) - COALESCE(s.sample_cnt, 0) AS diff_cnt,
    ROUND(
        (COALESCE(o.output_cnt, 0) - COALESCE(s.sample_cnt, 0)) * 100.0
        / NULLIF(s.sample_cnt, 0),
        4
    ) AS diff_pct
FROM sample_counts s
FULL JOIN output_counts o ON s.month = o.month
ORDER BY month;
"""
        return ValidationResult(
            category="样本量一致性",
            description="按月对比输出表与样本表记录数，差异应接近0",
            sql=sql,
            metrics=["month", "sample_cnt", "output_cnt", "diff_cnt", "diff_pct"],
            threshold_hint="diff_pct 应在 [-0.1%, +0.1%] 范围内（允许LEFT JOIN导致微量差异）"
        )

    # ==================== 2. 变量缺失率校验 ====================

    def generate_missing_rate_check(self, top_n: int = 20) -> ValidationResult:
        """
        按月统计：各变量的缺失率
        检查各变量缺失率是否正常（一般不应超过50%，核心变量不应超过10%）
        """
        # 为每个变量生成 COALESCE 判断
        null_checks = []
        for var in self.variables[:top_n]:
            null_checks.append(
                f"    SUM(CASE WHEN {var} IS NULL OR {var} = -999999 THEN 1 ELSE 0 END) AS {var}_null_cnt"
            )

        # 生成缺失率计算列
        rate_cols = []
        for var in self.variables[:top_n]:
            rate_cols.append(
                f"    ROUND({var}_null_cnt * 100.0 / total_cnt, 4) AS {var}_missing_pct"
            )

        null_checks_str = ",\n".join(null_checks) if null_checks else "    0 AS placeholder"
        rate_cols_str = ",\n".join(rate_cols) if rate_cols else "    0 AS placeholder"

        sql = f"""-- 2. 变量缺失率校验
-- 按月统计各变量缺失率，重点关注缺失率异常的变量

WITH monthly_stats AS (
    SELECT
        CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT) AS month,
        COUNT(1) AS total_cnt,
{null_checks_str}
    FROM {self.output_table}
    GROUP BY CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT)
)
SELECT
    month,
    total_cnt,
{rate_cols_str}
FROM monthly_stats
ORDER BY month;
"""
        return ValidationResult(
            category="变量缺失率",
            description=f"按月统计各变量缺失率，展示缺失率最高的前{top_n}个变量",
            sql=sql,
            metrics=["month", "total_cnt"] + [f"{v}_missing_pct" for v in self.variables[:top_n]],
            threshold_hint="核心变量缺失率应 < 10%，一般变量 < 50%，全为-999999表示该变量全空"
        )

    def generate_high_missing_summary(self, threshold: float = 50.0) -> ValidationResult:
        """
        汇总：缺失率超过阈值的变量清单
        """
        cases = []
        for i, var in enumerate(self.variables):
            cases.append(
                f"        SUM(CASE WHEN {var} IS NULL OR {var} = -999999 THEN 1 ELSE 0 END) AS null_cnt_{i}"
            )
        cases_str = ",\n".join(cases)

        explode_items = []
        for i, var in enumerate(self.variables):
            explode_items.append(f"    STRUCT('{var}', null_cnt_{i})")
        explode_str = ",\n".join(explode_items)

        sql = f"""-- 2.1 高缺失率变量汇总
-- 找出缺失率超过 {threshold}% 的变量

SELECT
    variable_name,
    total_cnt,
    null_cnt,
    ROUND(null_cnt * 100.0 / total_cnt, 4) AS missing_pct
FROM (
    SELECT
        COUNT(1) AS total_cnt,
{cases_str}
    FROM {self.output_table}
) t
LATERAL VIEW EXPLODE(ARRAY(
{explode_str}
)) tbl AS variable_name, null_cnt
WHERE ROUND(null_cnt * 100.0 / total_cnt, 4) >= {threshold}
ORDER BY missing_pct DESC;
"""
        return ValidationResult(
            category="高缺失率变量",
            description=f"找出缺失率超过 {threshold}% 的变量清单",
            sql=sql,
            metrics=["variable_name", "total_cnt", "null_cnt", "missing_pct"],
            threshold_hint=f"missing_pct >= {threshold}% 的变量需要特别关注"
        )

    # ==================== 3. 数据波动校验 ====================

    def generate_value_distribution_check(self, key_variables: Optional[List[str]] = None) -> ValidationResult:
        """
        按月统计：关键变量的均值、标准差、最小值、最大值、中位数
        检查数据波动是否正常（跨月标准差不应剧烈变化）
        """
        check_vars = key_variables or self.variables[:10]  # 默认前10个变量

        stats_parts = []
        for var in check_vars:
            stats_parts.append(
                f"    ROUND(AVG({var}), 6) AS {var}_avg,\n"
                f"    ROUND(STDDEV_POP({var}), 6) AS {var}_std,\n"
                f"    MIN({var}) AS {var}_min,\n"
                f"    MAX({var}) AS {var}_max,\n"
                f"    ROUND(PERCENTILE_APPROX(CAST({var} AS DOUBLE), 0.5), 6) AS {var}_median"
            )
        stats_str = ",\n".join(stats_parts) if stats_parts else "    0 AS placeholder"

        sql = f"""-- 3. 数据波动校验
-- 按月统计关键变量的均值、标准差、分位数，检查跨月波动是否正常

SELECT
    CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT) AS month,
    COUNT(1) AS cnt,
{stats_str}
FROM {self.output_table}
GROUP BY CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT)
ORDER BY month;
"""
        return ValidationResult(
            category="数据波动",
            description="按月统计关键变量的均值、标准差、分位数，监控跨月波动",
            sql=sql,
            metrics=["month", "cnt"] + [f"{v}_{s}" for v in check_vars for s in ['avg', 'std', 'min', 'max', 'median']],
            threshold_hint="跨月均值变化不应超过 ±20%，标准差变化不应超过 ±30%"
        )

    def generate_month_over_month_change(self, key_variables: Optional[List[str]] = None) -> ValidationResult:
        """
        环比变化：计算各变量均值的月度环比变化率
        """
        check_vars = key_variables or self.variables[:10]

        avg_cols = []
        for var in check_vars:
            avg_cols.append(f"        ROUND(AVG({var}), 6) AS {var}_avg")
        avg_str = ",\n".join(avg_cols)

        change_cols = []
        for var in check_vars:
            change_cols.append(
                f"        {var}_avg,\n"
                f"        LAG({var}_avg) OVER (ORDER BY month) AS {var}_prev_avg"
            )
        change_str = ",\n".join(change_cols)

        pct_cols = []
        for var in check_vars:
            pct_cols.append(
                f"    {var}_avg,\n"
                f"    {var}_prev_avg,\n"
                f"    ROUND(({var}_avg - {var}_prev_avg) * 100.0 / NULLIF({var}_prev_avg, 0), 4) AS {var}_mom_pct"
            )
        pct_str = ",\n".join(pct_cols)

        sql = f"""-- 3.1 环比波动检测
-- 计算各变量均值的月度环比变化率

WITH monthly_avg AS (
    SELECT
        CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT) AS month,
{avg_str}
    FROM {self.output_table}
    GROUP BY CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT)
),
monthly_change AS (
    SELECT
        month,
        LAG(month) OVER (ORDER BY month) AS prev_month,
{change_str}
    FROM monthly_avg
)
SELECT
    month,
    prev_month,
{pct_str}
FROM monthly_change
ORDER BY month;
"""
        return ValidationResult(
            category="环比波动",
            description="计算各变量均值的月度环比变化率",
            sql=sql,
            metrics=["month", "prev_month"] + [f"{v}_mom_pct" for v in check_vars],
            threshold_hint="环比变化率超过 ±30% 需要关注，超过 ±50% 需要排查"
        )

    # ==================== 4. 主键唯一性校验 ====================

    def generate_primary_key_uniqueness(self) -> ValidationResult:
        """
        检查输出表主键是否唯一
        """
        sql = f"""-- 4. 主键唯一性校验
-- 检查输出表主键({self.primary_key})是否存在重复

SELECT
    '重复记录数' AS check_item,
    COUNT(1) AS cnt
FROM (
    SELECT {self.primary_key}
    FROM {self.output_table}
    GROUP BY {self.primary_key}
    HAVING COUNT(1) > 1
) t

UNION ALL

SELECT
    '总记录数' AS check_item,
    COUNT(1) AS cnt
FROM {self.output_table}

UNION ALL

SELECT
    '唯一主键数' AS check_item,
    COUNT(DISTINCT {self.primary_key}) AS cnt
FROM {self.output_table};
"""
        return ValidationResult(
            category="主键唯一性",
            description=f"检查输出表主键 {self.primary_key} 是否存在重复",
            sql=sql,
            metrics=["check_item", "cnt"],
            threshold_hint="重复记录数应为0，总记录数应等于唯一主键数"
        )

    # ==================== 5. 评分分布校验 ====================

    def generate_score_distribution(self) -> ValidationResult:
        """
        按月统计：评分分布（均值、标准差、分位数、全空占比）
        """
        sql = f"""-- 5. 评分分布校验
-- 按月统计评分卡分布及全空样本占比

SELECT
    CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT) AS month,
    COUNT(1) AS total_cnt,
    SUM(CASE WHEN all_null_flag = 1 THEN 1 ELSE 0 END) AS all_null_cnt,
    ROUND(SUM(CASE WHEN all_null_flag = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(1), 4) AS all_null_pct,
    ROUND(AVG({self.score_field}), 4) AS score_avg,
    ROUND(STDDEV_POP({self.score_field}), 4) AS score_std,
    MIN({self.score_field}) AS score_min,
    MAX({self.score_field}) AS score_max,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.05), 4) AS score_p05,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.25), 4) AS score_p25,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.5), 4) AS score_p50,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.75), 4) AS score_p75,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.95), 4) AS score_p95
FROM {self.output_table}
GROUP BY CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT)
ORDER BY month;
"""
        return ValidationResult(
            category="评分分布",
            description="按月统计评分卡分布及全空样本占比",
            sql=sql,
            metrics=["month", "total_cnt", "all_null_cnt", "all_null_pct", "score_avg", "score_std", "score_min", "score_max", "score_p05", "score_p25", "score_p50", "score_p75", "score_p95"],
            threshold_hint="all_null_pct 一般 < 5%；score_avg 跨月波动应 < 30分；score_p50 应在 400-700 之间"
        )

    def generate_score_range_distribution(self) -> ValidationResult:
        """
        评分区间分布（用于PSI计算）
        """
        sql = f"""-- 5.1 评分区间分布
-- 按月统计评分区间分布，可用于PSI稳定性计算

SELECT
    CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT) AS month,
    CASE
        WHEN {self.score_field} < 0 THEN '01: <0(无效)'
        WHEN {self.score_field} < 400 THEN '02: [0,400)'
        WHEN {self.score_field} < 500 THEN '03: [400,500)'
        WHEN {self.score_field} < 600 THEN '04: [500,600)'
        WHEN {self.score_field} < 700 THEN '05: [600,700)'
        WHEN {self.score_field} < 800 THEN '06: [700,800)'
        ELSE '07: >=800'
    END AS score_bucket,
    COUNT(1) AS cnt,
    ROUND(COUNT(1) * 100.0 / SUM(COUNT(1)) OVER (PARTITION BY CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT)), 4) AS pct
FROM {self.output_table}
GROUP BY
    CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT),
    CASE
        WHEN {self.score_field} < 0 THEN '01: <0(无效)'
        WHEN {self.score_field} < 400 THEN '02: [0,400)'
        WHEN {self.score_field} < 500 THEN '03: [400,500)'
        WHEN {self.score_field} < 600 THEN '04: [500,600)'
        WHEN {self.score_field} < 700 THEN '05: [600,700)'
        WHEN {self.score_field} < 800 THEN '06: [700,800)'
        ELSE '07: >=800'
    END
ORDER BY month, score_bucket;
"""
        return ValidationResult(
            category="评分区间",
            description="按月统计评分区间分布，用于PSI稳定性计算",
            sql=sql,
            metrics=["month", "score_bucket", "cnt", "pct"],
            threshold_hint="各区间占比跨月变化不应超过 ±5%"
        )

    # ==================== 6. 变量覆盖度校验 ====================
        return ValidationResult(
            category="环比波动",
            description="计算各变量均值的月度环比变化率",
            sql=sql,
            metrics=["month", "prev_month"] + [f"{v}_mom_pct" for v in check_vars],
            threshold_hint="环比变化率超过 ±30% 需要关注，超过 ±50% 需要排查"
        )

    # ==================== 4. 主键唯一性校验 ====================

    def generate_primary_key_uniqueness(self) -> ValidationResult:
        """
        检查输出表主键是否唯一
        """
        sql = f"""-- 4. 主键唯一性校验
-- 检查输出表主键({self.primary_key})是否存在重复

SELECT
    '重复记录数' AS check_item,
    COUNT(1) AS cnt
FROM (
    SELECT {self.primary_key}
    FROM {self.output_table}
    GROUP BY {self.primary_key}
    HAVING COUNT(1) > 1
) t

UNION ALL

SELECT
    '总记录数' AS check_item,
    COUNT(1) AS cnt
FROM {self.output_table}

UNION ALL

SELECT
    '唯一主键数' AS check_item,
    COUNT(DISTINCT {self.primary_key}) AS cnt
FROM {self.output_table};
"""
        return ValidationResult(
            category="主键唯一性",
            description=f"检查输出表主键 {self.primary_key} 是否存在重复",
            sql=sql,
            metrics=["check_item", "cnt"],
            threshold_hint="重复记录数应为0，总记录数应等于唯一主键数"
        )

    # ==================== 5. 评分分布校验 ====================

    def generate_score_distribution(self) -> ValidationResult:
        """
        按月统计：评分分布（均值、标准差、分位数、全空占比）
        """
        sql = f"""-- 5. 评分分布校验
-- 按月统计评分卡分布及全空样本占比

SELECT
    CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT) AS month,
    COUNT(1) AS total_cnt,
    SUM(CASE WHEN all_null_flag = 1 THEN 1 ELSE 0 END) AS all_null_cnt,
    ROUND(SUM(CASE WHEN all_null_flag = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(1), 4) AS all_null_pct,
    ROUND(AVG({self.score_field}), 4) AS score_avg,
    ROUND(STDDEV_POP({self.score_field}), 4) AS score_std,
    MIN({self.score_field}) AS score_min,
    MAX({self.score_field}) AS score_max,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.05), 4) AS score_p05,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.25), 4) AS score_p25,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.5), 4) AS score_p50,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.75), 4) AS score_p75,
    ROUND(PERCENTILE_APPROX(CAST({self.score_field} AS DOUBLE), 0.95), 4) AS score_p95
FROM {self.output_table}
GROUP BY CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT)
ORDER BY month;
"""
        return ValidationResult(
            category="评分分布",
            description="按月统计评分卡分布及全空样本占比",
            sql=sql,
            metrics=["month", "total_cnt", "all_null_cnt", "all_null_pct", "score_avg", "score_std", "score_min", "score_max", "score_p05", "score_p25", "score_p50", "score_p75", "score_p95"],
            threshold_hint="all_null_pct 一般 < 5%；score_avg 跨月波动应 < 30分；score_p50 应在 400-700 之间"
        )

    def generate_score_range_distribution(self) -> ValidationResult:
        """
        评分区间分布（用于PSI计算）
        """
        sql = f"""-- 5.1 评分区间分布
-- 按月统计评分区间分布，可用于PSI稳定性计算

SELECT
    CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT) AS month,
    CASE
        WHEN {self.score_field} < 0 THEN '01: <0(无效)'
        WHEN {self.score_field} < 400 THEN '02: [0,400)'
        WHEN {self.score_field} < 500 THEN '03: [400,500)'
        WHEN {self.score_field} < 600 THEN '04: [500,600)'
        WHEN {self.score_field} < 700 THEN '05: [600,700)'
        WHEN {self.score_field} < 800 THEN '06: [700,800)'
        ELSE '07: >=800'
    END AS score_bucket,
    COUNT(1) AS cnt,
    ROUND(COUNT(1) * 100.0 / SUM(COUNT(1)) OVER (PARTITION BY CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT)), 4) AS pct
FROM {self.output_table}
GROUP BY
    CAST(SUBSTR(CAST({self.date_field} AS STRING), 1, 6) AS INT),
    CASE
        WHEN {self.score_field} < 0 THEN '01: <0(无效)'
        WHEN {self.score_field} < 400 THEN '02: [0,400)'
        WHEN {self.score_field} < 500 THEN '03: [400,500)'
        WHEN {self.score_field} < 600 THEN '04: [500,600)'
        WHEN {self.score_field} < 700 THEN '05: [600,700)'
        WHEN {self.score_field} < 800 THEN '06: [700,800)'
        ELSE '07: >=800'
    END
ORDER BY month, score_bucket;
"""
        return ValidationResult(
            category="评分区间",
            description="按月统计评分区间分布，用于PSI稳定性计算",
            sql=sql,
            metrics=["month", "score_bucket", "cnt", "pct"],
            threshold_hint="各区间占比跨月变化不应超过 ±5%"
        )

    # ==================== 6. 变量覆盖度校验 ====================