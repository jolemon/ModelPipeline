"""
模型打分 SQL 生成模块

负责生成模型打分SQL，包括：
- 空值填充
- 全空打标
- 模型打分
- 评分卡映射
"""

from typing import List, Optional, Dict, Any, Union
from pathlib import Path

import lightgbm as lgb

from src.core.config_loader import SQLConfig
from src.core.lgb2sql import Lgb2Sql


class ScoreGenerator:
    """模型打分SQL生成器"""

    def __init__(self, config: SQLConfig):
        """初始化模型打分SQL生成器

        Args:
            config: SQL配置对象
        """
        self.config = config

    @staticmethod
    def load_model(model_path: str) -> lgb.Booster:
        """加载 LightGBM 模型

        根据文件后缀自动选择加载方式：.model 使用 lgb.Booster，.pkl 使用 joblib。

        Args:
            model_path: 模型文件路径（.model / .pkl）

        Returns:
            lgb.Booster: 加载后的 Booster 对象

        Raises:
            ValueError: 不支持的模型格式时抛出
            Exception: joblib 或 lightgbm 加载失败时抛出
        """
        if model_path.endswith('.model'):
            return lgb.Booster(model_file=model_path)
        elif model_path.endswith('.pkl'):
            import joblib
            return joblib.load(model_path)
        else:
            raise ValueError(f"不支持的模型格式: {model_path}")

    def generate(self,
                 model_path: Optional[str] = None,
                 booster: Optional[lgb.Booster] = None,
                 keep_columns: Optional[List[str]] = None,
                 input_table: Optional[str] = None,
                 work_no: Optional[str] = None,
                 model_id: Optional[str] = None,
                 table_date: Optional[str] = None,
                 scorecard_shift: float = 533.903595,
                 scorecard_slope: float = 72.134752,
                 scorecard_round: int = 2,
                 round_decimal: int = 32) -> str:
        """
        生成模型打分SQL

        Args:
            model_path: 模型文件路径（.model / .pkl），与 booster 二选一
            booster: 已加载的 Booster 对象，与 model_path 二选一
            keep_columns: 保留列（主键等），默认 ['apply_no']
            input_table: 输入变量表名
            work_no: 工作编号
            model_id: 模型ID
            table_date: 日期
            scorecard_shift: 评分卡偏移量
            scorecard_slope: 评分卡斜率
            scorecard_round: 评分卡小数位
            round_decimal: 树阈值小数位精度

        Returns:
            完整打分SQL字符串

        Raises:
            ValueError: model_path 和 booster 均未提供
        """
        if booster is None:
            if model_path is None:
                raise ValueError("必须提供 model_path 或 booster 其中一个参数")
            booster = self.load_model(model_path)

        keep_columns = keep_columns or ['apply_no']
        work_no = work_no or self.config.work_no
        model_id = model_id or self.config.model_id
        table_date = table_date or self.config.get_date_str()

        # 计算额外样本字段
        extra_columns = None
        if self.config.output_include_sample_fields:
            sample_fields = self.config.sample_fields
            extra_columns = [f for f in sample_fields if f not in keep_columns]
            if not extra_columns:
                extra_columns = None

        # 使用 Lgb2Sql 生成打分SQL
        handler = Lgb2Sql()
        score_sql = handler.generate_full_score_sql(
            lgb_model=booster,
            keep_columns=keep_columns,
            sql_is_format=False,
            round_decimal=round_decimal,
            work_no=work_no,
            model_id=model_id,
            table_date=table_date,
            scorecard_shift=scorecard_shift,
            scorecard_slope=scorecard_slope,
            scorecard_round=scorecard_round,
            input_table=input_table,
            extra_columns=extra_columns,
            output_variables=self.config.output_variable_enabled,
            sort_by_importance=self.config.output_variable_sort_by_importance,
            top_n=self.config.output_variable_top_n,
        )

        return score_sql

    def get_created_tables(self,
                           work_no: Optional[str] = None,
                           model_id: Optional[str] = None,
                           table_date: Optional[str] = None) -> List[str]:
        """获取打分SQL创建的临时表列表

        Args:
            work_no: 工作编号，默认从配置读取
            model_id: 模型ID，默认从配置读取
            table_date: 日期字符串，默认从配置读取

        Returns:
            临时表名称列表
        """
        work_no = work_no or self.config.work_no
        model_id = model_id or self.config.model_id
        table_date = table_date or self.config.get_date_str()

        return [
            f"tmp_{work_no}_{table_date}_{model_id}_var_fillna",
            f"tmp_{work_no}_{table_date}_{model_id}_model_score",
            f"tmp_{work_no}_{table_date}_{model_id}_model_scorecard",
        ]
