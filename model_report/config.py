from dataclasses import dataclass


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

    # Labels
    target_label: str = "Mob6 30+"
    train_label: str = "训练集"
    test_label: str = "测试集"
    oot_label: str = "跨时间验证集"
    oos_label: str = "压测"

    # Sheet names
    sheet1_name: str = "模型设计"
    sheet2_name: str = "变量分析"
    sheet3_name: str = "模型表现"

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
        ]

    def get_feature_columns(self, df_columns: list) -> list:
        """Extract feature column names from DataFrame columns."""
        non_vars = set(self.get_non_variable_columns())
        return [c for c in df_columns if c not in non_vars]

    def resolve_score_column(self, df_columns: list) -> str:
        """Resolve the best available score column for metrics calculation.

        Returns score_col if present in df_columns, otherwise falls back to sc_score_col.
        """
        if self.score_col in df_columns:
            return self.score_col
        return self.sc_score_col
