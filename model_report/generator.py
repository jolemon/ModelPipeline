import pandas as pd
from model_report.config import ReportConfig
from model_report.metadata import load_variable_metadata
from model_report.writer import ExcelWriter
from model_report.sheets.model_design import build_model_design_sheet
from model_report.sheets.variable_analysis import build_variable_analysis_sheet
from model_report.sheets.model_performance import build_model_performance_sheet


class ReportGenerator:
    """Orchestrates the three sheet builders and writes the Excel report.

    Args:
        scorecard: Optional scorecard object implementing ScorecardProtocol.
                   If None, scorecard-dependent content is skipped.
        config: Optional ReportConfig with column mappings and labels.
    """

    def __init__(self, scorecard=None, config=None):
        self.scorecard = scorecard
        self.config = config if config is not None else ReportConfig()
        self._writer = ExcelWriter()
        self._metadata = {}

    def generate(self, data: pd.DataFrame, metadata_path=None) -> dict:
        """Generate all report sheets as structured data.

        If no scorecard is provided, Sheet 2 skips IV/KS/WOE from scorecard
        (still computes data-driven metrics) and Sheet 3 skips scorecard detail.
        """
        self._validate_data(data)
        self._metadata = load_variable_metadata(metadata_path)

        sheet1 = build_model_design_sheet(data, self.config)
        sheet2 = build_variable_analysis_sheet(data, self.scorecard, self.config, self._metadata)
        sheet3 = build_model_performance_sheet(data, self.scorecard, self.config)

        return {
            self.config.sheet1_name: sheet1,
            self.config.sheet2_name: sheet2,
            self.config.sheet3_name: sheet3,
        }

    def to_excel(self, output_path: str, data: pd.DataFrame,
                 metadata_path=None) -> None:
        """Generate report and write to Excel file."""
        sheets = self.generate(data, metadata_path)
        self._writer.write(output_path, sheets)

    def _validate_data(self, data: pd.DataFrame) -> None:
        """Validate that required columns exist."""
        required = [
            self.config.partition_col,
            self.config.flag_col,
            self.config.target_col,
            self.config.sc_score_col,
        ]

        missing = [col for col in required if col not in data.columns]
        if missing:
            raise ValueError(
                f"Missing required columns in data: {missing}. "
                f"Available columns: {list(data.columns)}"
            )

        target_vals = data[self.config.target_col].dropna().unique()
        if set(target_vals) - {0, 1}:
            raise ValueError(
                f"Target column '{self.config.target_col}' must contain only 0 and 1, "
                f"found: {sorted(target_vals)}"
            )

        flag_vals = data[self.config.flag_col].unique()
        if "train" not in flag_vals:
            raise ValueError(
                f"Data must contain 'train' in '{self.config.flag_col}' column. "
                f"Found: {sorted(flag_vals)}"
            )
