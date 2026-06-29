import pandas as pd
import numpy as np

from .config_loader import Config, VariableDef
from shared.utils import is_missing

_is_null = is_missing  # 向后兼容别名


class Comparator:
    def __init__(self, merged: pd.DataFrame, config: Config):
        self.df = merged
        self.config = config
        self.score_col = config.score_column
        self.score_online = merged[f"{self.score_col}_online"]
        self.score_offline = merged[f"{self.score_col}_offline"]

    def compare_scores(self) -> pd.Series:
        online_null = _is_null(self.score_online)
        offline_null = _is_null(self.score_offline)
        both_null = online_null & offline_null
        neither_null = ~online_null & ~offline_null

        online_num = pd.to_numeric(self.score_online, errors="coerce")
        offline_num = pd.to_numeric(self.score_offline, errors="coerce")
        close_match = (online_num - offline_num).abs() < 1e-3

        return both_null | (neither_null & close_match)

    def compare_variable(self, vardef: VariableDef) -> pd.Series:
        online_col = self.df[f"{vardef.name}_online"]
        offline_col = self.df[f"{vardef.name}_offline"]

        online_null = _is_null(online_col)
        offline_null = _is_null(offline_col)
        both_null = online_null & offline_null
        neither_null = ~online_null & ~offline_null

        if vardef.type == "enum":
            online_str = online_col.astype(str).str.strip()
            offline_str = offline_col.astype(str).str.strip()
            matched = online_str == offline_str
        else:
            online_num = pd.to_numeric(online_col, errors="coerce")
            offline_num = pd.to_numeric(offline_col, errors="coerce")

            if vardef.precision is not None:
                online_rounded = online_num.round(vardef.precision)
                offline_rounded = offline_num.round(vardef.precision)
            else:
                online_prec = _infer_precision(online_num)
                offline_prec = _infer_precision(offline_num)
                max_prec = max(online_prec, offline_prec)
                online_rounded = online_num.round(max_prec)
                offline_rounded = offline_num.round(max_prec)

            matched = online_rounded == offline_rounded

        return both_null | (neither_null & matched)

    def compare_all(self) -> dict[str, pd.Series]:
        results = {"score": self.compare_scores()}
        for vardef in self.config.variables:
            results[vardef.name] = self.compare_variable(vardef)
        return results


def _infer_precision(series: pd.Series) -> int:
    """Infer decimal precision from numeric series."""
    s = series.dropna()
    if len(s) == 0:
        return 0
    # Convert to string and count decimal places (avoid .str accessor compat issues)
    precisions = s.apply(lambda x: len(str(x).split(".")[1]) if "." in str(x) else None)
    precisions = precisions.dropna()
    if len(precisions) == 0:
        return 0
    return int(precisions.max())
