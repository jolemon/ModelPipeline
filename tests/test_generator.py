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
