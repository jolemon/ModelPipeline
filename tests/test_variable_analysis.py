import pytest
import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.sheets.variable_analysis import build_variable_analysis_sheet


class TestBuildVariableAnalysisSheet:
    def test_returns_two_sections(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        metadata = {"feat_a": {"变量解释含义": "test var a", "来源": "src_a", "表描述": "desc_a"}}
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, metadata)
        assert "变量总览" in result
        assert "Top10 单变量 WOE 分箱分析" in result

    def test_overview_columns(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, {})
        df = result["变量总览"]
        expected = ["序号", "变量名", "变量解释含义", "来源", "表描述", "数据类型"]
        for col in expected:
            assert col in df.columns

    def test_overview_iv_train_column(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, {})
        df = result["变量总览"]
        assert "iv_train" in df.columns
        assert "iv_oot" in df.columns

    def test_overview_uses_metadata(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        metadata = {"feat_a": {"变量解释含义": "test meaning", "来源": "test_source", "表描述": "test_desc"}}
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, metadata)
        df = result["变量总览"]
        row = df[df["变量名"] == "feat_a"].iloc[0]
        assert row["变量解释含义"] == "test meaning"

    def test_overview_missing_metadata_fills_empty(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, {})
        df = result["变量总览"]
        row = df[df["变量名"] == "feat_a"].iloc[0]
        assert row["变量解释含义"] == ""

    def test_top10_woe_has_variables(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
            top_n_vars=3,
        )
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, {})
        top10 = result["Top10 单变量 WOE 分箱分析"]
        assert len(top10) <= 3

    def test_scorecard_restricts_variables(self, small_df, mock_scorecard):
        """When scorecard provides var_names, only those are analyzed."""
        # Mock scorecard returns only ['feat_a'] as model variables
        mock_scorecard.get_var_names.return_value = ["feat_a"]
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        # small_df has feat_a, feat_b, feat_c
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, {})
        overview = result["变量总览"]
        var_names = overview["变量名"].tolist()
        assert var_names == ["feat_a"]

    def test_no_scorecard_all_variables(self, small_df):
        """Without scorecard, all feature columns are analyzed."""
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_variable_analysis_sheet(small_df, None, config, {})
        overview = result["变量总览"]
        var_names = overview["变量名"].tolist()
        # small_df has feat_a, feat_b, feat_c → all should be present
        assert len(var_names) == 3
        assert "feat_a" in var_names
        assert "feat_b" in var_names
        assert "feat_c" in var_names
