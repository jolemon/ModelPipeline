from typing import Protocol, runtime_checkable
import pandas as pd
import pickle


@runtime_checkable
class ScorecardProtocol(Protocol):
    """Protocol defining the interface report generator expects from a scorecard."""

    def get_var_names(self) -> list[str]:
        """Return list of all variable names."""
        ...

    def get_bins(self, var: str) -> pd.Series:
        """Return bin intervals for a variable."""
        ...

    def get_woe_table(self, var: str) -> pd.DataFrame:
        """Return WOE table DataFrame for a variable."""
        ...

    def get_iv_table(self) -> pd.Series:
        """Return IV values indexed by variable name."""
        ...

    def get_ks_table(self) -> pd.Series:
        """Return KS values indexed by variable name."""
        ...

    def get_model_summary(self) -> pd.DataFrame:
        """Return model coefficients/Wald stats DataFrame."""
        ...

    def get_scorecard(self) -> pd.DataFrame:
        """Return scorecard DataFrame with name/left/right/score."""
        ...

    def get_missing_dict(self) -> dict:
        """Return variable -> fill_value mapping."""
        ...

    def get_dropped_vars(self) -> list[str]:
        """Return list of variables dropped during modeling."""
        ...


class PickledScorecardAdapter:
    """Adapter that loads a .pkl scorecard and exposes the protocol."""

    def __init__(self, pkl_path: str):
        self.pkl_path = pkl_path
        self._scorecard = self._load()

    def _load(self):
        with open(self.pkl_path, "rb") as f:
            return pickle.load(f)

    def get_var_names(self) -> list[str]:
        if hasattr(self._scorecard, "varlist"):
            return list(self._scorecard.varlist)
        return []

    def get_bins(self, var: str) -> pd.Series:
        if hasattr(self._scorecard, "bins"):
            return self._scorecard.bins.get(var, pd.Series([], name="bins"))
        return pd.Series([], name="bins")

    def get_woe_table(self, var: str) -> pd.DataFrame:
        if hasattr(self._scorecard, "woetables"):
            return self._scorecard.woetables.get(var, pd.DataFrame())
        return pd.DataFrame()

    def get_iv_table(self) -> pd.Series:
        if hasattr(self._scorecard, "ivtable"):
            return self._scorecard.ivtable
        return pd.Series([], name="IV")

    def get_ks_table(self) -> pd.Series:
        if hasattr(self._scorecard, "ks_table"):
            return self._scorecard.ks_table
        return pd.Series([], name="KS")

    def get_model_summary(self) -> pd.DataFrame:
        if hasattr(self._scorecard, "show_model_result"):
            return self._scorecard.show_model_result()
        return pd.DataFrame()

    def get_scorecard(self) -> pd.DataFrame:
        if hasattr(self._scorecard, "score_card_result"):
            return self._scorecard.score_card_result
        return pd.DataFrame()

    def get_missing_dict(self) -> dict:
        if hasattr(self._scorecard, "binner") and hasattr(self._scorecard.binner, "missing_dict"):
            return self._scorecard.binner.missing_dict
        return {}

    def get_dropped_vars(self) -> list[str]:
        if hasattr(self._scorecard, "dropped_vars"):
            return self._scorecard.dropped_vars
        return []
