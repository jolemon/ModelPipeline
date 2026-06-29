"""
打分 SQL 生成 Stage

职责：加载模型，生成打分SQL（空值填充 -> 全空打标 -> 打分 -> 评分卡）
"""

from typing import Dict, List, Optional


class ScoreGenerationStage:
    """打分SQL生成 Stage：加载模型，生成打分SQL"""

    def execute(self, ctx,
                model_path: str,
                keep_columns: Optional[List[str]] = None,
                input_table: Optional[str] = None,
                work_no: Optional[str] = None,
                model_id: Optional[str] = None,
                table_date: Optional[str] = None,
                scorecard_shift: float = 533.903595,
                scorecard_slope: float = 72.134752,
                scorecard_round: int = 2,
                round_decimal: int = 32,
                verbose: bool = True) -> str:
        """生成模型打分SQL

        Args:
            ctx: PipelineContext
            model_path: 模型文件路径
            keep_columns: 保留列（主键等）
            input_table: 输入变量表名
            work_no: 工作编号
            model_id: 模型ID
            table_date: 日期字符串
            scorecard_shift: 评分卡偏移量
            scorecard_slope: 评分卡斜率
            scorecard_round: 评分卡小数位
            round_decimal: 树阈值小数位精度
            verbose: 是否打印详细日志

        Returns:
            完整打分SQL字符串
        """
        if verbose:
            print("\n" + "=" * 70)
            print(" 步骤5: 生成模型打分SQL（空值填充 -> 全空打标 -> 打分 -> 评分卡） ")
            print("=" * 70)

        keep_columns = keep_columns or ['apply_no']
        work_no = work_no or ctx.config.work_no
        model_id = model_id or ctx.config.model_id
        table_date = table_date or ctx.config.get_date_str()

        if verbose:
            print(f"\n[打分参数]")
            print(f"  保留列:     {keep_columns}")
            print(f"  输入表:     {input_table or '(自动命名)'}")
            print(f"  工作编号:   {work_no}")
            print(f"  模型ID:     {model_id}")
            print(f"  日期:       {table_date}")
            print(f"  评分卡偏移: {scorecard_shift}")
            print(f"  评分卡斜率: {scorecard_slope}")
            print(f"  阈值精度:   {round_decimal} 位小数")
            print(f"\n[加载模型]")
            print(f"  模型路径: {model_path}")

        # 加载模型
        try:
            booster = ctx.score_generator.load_model(model_path)
            if verbose:
                print(f"  /:em_209:/ 模型加载成功: {booster.num_feature()} 特征, {booster.num_trees()} 棵树")
        except Exception as e:
            if verbose:
                print(f"  [FAIL] 模型加载失败: {e}")
            from src.pipeline_pkg.pipeline_core import PipelineError
            raise PipelineError(f"模型加载失败: {e}")

        score_sql = ctx.score_generator.generate(
            booster=booster,
            keep_columns=keep_columns,
            input_table=input_table,
            work_no=work_no,
            model_id=model_id,
            table_date=table_date,
            scorecard_shift=scorecard_shift,
            scorecard_slope=scorecard_slope,
            scorecard_round=scorecard_round,
            round_decimal=round_decimal
        )

        tables_created = ctx.score_generator.get_created_tables(work_no, model_id, table_date)

        if verbose:
            print(f"\n[生成结果]")
            print(f"  SQL长度:      {len(score_sql)} 字符")
            print(f"  创建临时表:   {len(tables_created)} 张")
            for tbl in tables_created:
                print(f"    - {tbl}")
            print(f"\n/:em_209:/ 打分SQL生成完成")

        ctx.score_sql = score_sql
        return score_sql
