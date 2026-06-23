import pytest
import tempfile
from pathlib import Path
import pandas as pd
from model_report.config import ReportConfig
from model_report.generator import ReportGenerator


class TestReportGenerator:
    def test_generate_returns_dict(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(mock_scorecard, config)
        result = gen.generate(small_df)
        assert isinstance(result, dict)
        assert config.sheet1_name in result
        assert config.sheet2_name in result
        assert config.sheet3_name in result

    def test_generate_validates_required_columns(self, mock_scorecard):
        config = ReportConfig(target_col="mob6_30", flag_col="data_flag")
        gen = ReportGenerator(mock_scorecard, config)
        df = pd.DataFrame({"wrong_col": [1, 2, 3]})
        with pytest.raises(ValueError):
            gen.generate(df)

    def test_to_excel_creates_file(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(mock_scorecard, config)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            gen.to_excel(output_path, small_df)
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0
        finally:
            Path(output_path).unlink()

    def test_metadata_loading(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(mock_scorecard, config)
        result = gen.generate(small_df)
        assert isinstance(result, dict)

    def test_generate_without_scorecard(self, small_df):
        """Without scorecard, all sheets should still generate."""
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(None, config)
        result = gen.generate(small_df)
        assert config.sheet1_name in result
        assert config.sheet2_name in result
        assert config.sheet3_name in result

    def test_without_scorecard_woe_tables_computed(self, small_df):
        """Without scorecard, WOE tables are still computed from data."""
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
            top_n_vars=3,
        )
        gen = ReportGenerator(None, config)
        result = gen.generate(small_df)
        sheet2 = result[config.sheet2_name]
        assert len(sheet2["top10_woe_bins"]) > 0

    def test_without_scorecard_iv_train_computed(self, small_df):
        """Without scorecard, iv_train and ks_train are computed from data."""
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(None, config)
        result = gen.generate(small_df)
        overview = result[config.sheet2_name]["ivar_ks_psi_overview"]
        # iv/ks computed from data — should be non-empty numeric strings
        assert overview["iv_train"].iloc[0] != ""
        assert overview["ks_train"].iloc[0] != ""

    def test_without_scorecard_no_detail(self, small_df):
        """Without scorecard, scorecard_detail should be None."""
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(None, config)
        result = gen.generate(small_df)
        sheet3 = result[config.sheet3_name]
        assert sheet3["scorecard_detail"] is None or sheet3["scorecard_detail"].empty

    def test_to_excel_without_scorecard(self, small_df):
        """Without scorecard, Excel should still be generated."""
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(None, config)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name
        try:
            gen.to_excel(output_path, small_df)
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0
        finally:
            Path(output_path).unlink()
