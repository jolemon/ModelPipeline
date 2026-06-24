from dataclasses import dataclass, field


@dataclass
class ReportConfig:
    # Column name mappings
    partition_col: str = "part_id"
    cust_col: str = "cert_no"
    date_col: str = "loan_date"
    target_col: str = "mob6_30"
    flag_col: str = "data_flag"
    score_col: str = "pred_score"
    sc_score_col: str = "scorecard_score"

    # Extra columns to exclude from variable analysis
    exclude_columns: list = field(default_factory=list)

    # Optional: loan amount column for amount-weighted AUC/KS
    loan_amount_col: str = ""

    # Labels
    target_label: str = "Mob6 30+"
    train_label: str = "训练集"
    test_label: str = "测试集"
    oot_label: str = "跨时间验证集"
    oos_label: str = "压测"

    # Sheet names
    sheet1_name: str = "1.模型设计"
    sheet2_name: str = "2.变量分析"
    sheet3_name: str = "3.模型表现"

    # Thresholds
    top_n_vars: int = 10

    @property
    def flag_labels(self) -> dict:
        return {
            "train": self.train_label,
            "test": self.test_label,
            "oot": self.oot_label,
            "oos": self.oos_label,
        }

    def get_non_variable_columns(self) -> list:
        """Return column names that should be excluded from variable analysis."""
        return [
            self.partition_col,
            self.cust_col,
            self.date_col,
            self.target_col,
            self.flag_col,
            self.score_col,
            self.sc_score_col,
        ] + list(self.exclude_columns)

    def get_feature_columns(self, df_columns: list) -> list:
        """Extract feature column names from DataFrame columns."""
        non_vars = set(self.get_non_variable_columns())
        return [c for c in df_columns if c not in non_vars]

    # Common score column name candidates (checked when configured cols not found)
    _SCORE_CANDIDATES = ["scorecard_score", "score", "pred_score", "prob"]

    def resolve_score_column(self, df_columns: list) -> str:
        """Resolve the best available score column for metrics calculation.

        Checks sc_score_col first, then score_col, then common candidates.
        """
        if self.sc_score_col in df_columns:
            return self.sc_score_col
        if self.score_col in df_columns:
            return self.score_col
        for candidate in self._SCORE_CANDIDATES:
            if candidate in df_columns:
                return candidate
        return self.sc_score_col  # Return default even if missing

    def resolve_sc_score_column(self, df_columns: list) -> str:
        """Resolve the scorecard score column (used for binning)."""
        if self.sc_score_col in df_columns:
            return self.sc_score_col
        for candidate in self._SCORE_CANDIDATES:
            if candidate in df_columns:
                return candidate
        return self.sc_score_col
