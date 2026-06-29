import pytest
import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.sheets.model_design import build_model_design_sheet


class TestBuildModelDesignSheet:
    def test_returns_two_dataframes(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        assert "1.1 样本分区分布" in result
        assert "1.2 样本建模分" in result
        assert "1.3 模型效果汇总" in result

    def test_partition_distribution_columns(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        df = result["1.1 样本分区分布"]
        expected_cols = ["样本数据集划分标签", "样本分区", "好", "坏", "总数", "坏占比"]
        for col in expected_cols:
            assert col in df.columns

    def test_partition_distribution_has_total_row(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        df = result["1.1 样本分区分布"]
        assert "总计" in df["样本数据集划分标签"].values

    def test_modeling_score_fixed_rows(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        df = result["1.2 样本建模分"]
        labels = df["样本数据集划分标签"].tolist()
        assert "训练集" in labels
        assert "测试集" in labels
        assert "跨时间验证集" in labels
        assert "总计" in labels

    def test_bad_rate_format(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        df = result["1.1 样本分区分布"]
        mask = df["样本数据集划分标签"] != "总计"
        bad_rate_val = df.loc[mask, "坏占比"].iloc[0]
        assert isinstance(bad_rate_val, str)
        assert "%" in bad_rate_val
