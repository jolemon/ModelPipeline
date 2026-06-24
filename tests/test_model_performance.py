import pytest
import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.sheets.model_performance import build_model_performance_sheet


class TestBuildModelPerformanceSheet:
    def test_returns_all_sections(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        assert "3.1 评分卡详情" in result
        assert "3.2 建模样本集效果" in result
        assert "3.3 回溯效果" in result
        assert "3.4 模型10分档表现" in result

    def test_scorecard_detail_columns(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        df = result["3.1 评分卡详情"]
        expected_cols = ["Parameter", "Estimate", "Std-Error", "Wald-Chi2",
                         "P-value", "P-value-num", "Std", "Std-Estimate", "VIF"]
        for col in expected_cols:
            assert col in df.columns

    def test_sample_effect_columns(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        df = result["3.2 建模样本集效果"]
        expected_cols = ["样本集", "观察点月", "样本标签", "总", "好", "坏", "坏占比", "KS", "AUC"]
        for col in expected_cols:
            assert col in df.columns

    def test_backtest_has_partition_rows(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        df = result["3.3 回溯效果"]
        assert len(df) >= 2

    def test_bin_performance(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        bin_perf = result["3.4 模型10分档表现"]
        assert len(bin_perf) > 0
