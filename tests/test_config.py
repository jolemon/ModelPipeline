import pytest
from model_report.config import ReportConfig


class TestReportConfig:
    def test_default_values(self):
        cfg = ReportConfig()
        assert cfg.partition_col == "part_id"
        assert cfg.target_col == "mob6_30"
        assert cfg.flag_col == "data_flag"
        assert cfg.score_col == "pred_score"
        assert cfg.sc_score_col == "scorecard_score"
        assert cfg.top_n_vars == 10

    def test_custom_override(self):
        cfg = ReportConfig(target_col="target_mob6_30", top_n_vars=5)
        assert cfg.target_col == "target_mob6_30"
        assert cfg.top_n_vars == 5
        assert cfg.partition_col == "part_id"

    def test_flag_labels(self):
        cfg = ReportConfig()
        assert cfg.flag_labels == {
            "train": "训练集",
            "test": "测试集",
            "oot": "跨时间验证集",
            "oos": "压测",
        }

    def test_non_variable_columns(self):
        cfg = ReportConfig()
        non_vars = cfg.get_non_variable_columns()
        for col in ["part_id", "cert_no", "loan_date", "mob6_30", "data_flag",
                     "pred_score", "scorecard_score"]:
            assert col in non_vars

    def test_resolve_score_column_prefers_sc_score(self):
        cfg = ReportConfig()
        df_cols = ["part_id", "mob6_30", "pred_score", "scorecard_score"]
        # sc_score_col takes priority
        assert cfg.resolve_score_column(df_cols) == "scorecard_score"

    def test_resolve_score_column_fallback_to_score(self):
        cfg = ReportConfig()
        df_cols = ["part_id", "mob6_30", "pred_score"]
        # sc_score_col not in df, falls back to score_col
        assert cfg.resolve_score_column(df_cols) == "pred_score"

    def test_resolve_score_column_neither(self):
        cfg = ReportConfig()
        df_cols = ["part_id", "mob6_30"]
        # neither sc_score_col nor score_col exists, returns score_col
        assert cfg.resolve_score_column(df_cols) == "pred_score"
