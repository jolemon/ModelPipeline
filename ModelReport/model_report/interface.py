from typing import Protocol, runtime_checkable
import pandas as pd
import numpy as np
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
    """Adapter that loads a .pkl scorecard file and exposes ScorecardProtocol.

    Navigates the Scorecard → Binner hierarchy from scorecard_jsb.py.
    Supports loading a Scorecard object (has .binner) or a Binner directly.
    """

    def __init__(self, pkl_path: str):
        self.pkl_path = pkl_path
        obj = self._load_file(pkl_path)
        self._init_from_obj(obj)

    @classmethod
    def _from_object(cls, obj):
        """Create adapter from an already-loaded object (for testing)."""
        adapter = cls.__new__(cls)
        adapter.pkl_path = None
        adapter._init_from_obj(obj)
        return adapter

    def _load_file(self, path):
        with open(path, "rb") as f:
            return pickle.load(f)

    def _init_from_obj(self, obj):
        # Locate Binner and Scorecard from the object hierarchy
        self._scorecard = self._find_scorecard(obj)
        self._binner = self._find_binner(obj)

        if self._binner is None:
            raise ValueError(
                f"Loaded object of type {type(obj).__name__} does not appear "
                f"to be a Scorecard or Binner. Expected an object with 'binner' "
                f"attribute (Scorecard) or 'woetables'/'ivtable' (Binner)."
            )

        # Pre-compute KS from WOE tables (Binner has no ks_table)
        self._ks_table = self._extract_ks_from_woe()

    @staticmethod
    def _find_scorecard(obj):
        """Locate Scorecard from loaded object."""
        # Direct Scorecard instance: has binner AND model_result or show_model_result
        if hasattr(obj, "binner") and (
            hasattr(obj, "model_result") or hasattr(obj, "show_model_result")
        ):
            return obj
        return None

    @staticmethod
    def _find_binner(obj):
        """Locate Binner from loaded object."""
        # Via Scorecard
        if hasattr(obj, "binner"):
            inner = obj.binner
            if hasattr(inner, "woetables") and hasattr(inner, "ivtable"):
                return inner
        # Direct Binner
        if hasattr(obj, "woetables") and hasattr(obj, "ivtable"):
            return obj
        return None

    def _extract_ks_from_woe(self) -> pd.Series:
        """Compute per-variable KS from WOE tables cumulative columns."""
        ks_vals = {}
        for var, woe_df in self._binner.woetables.items():
            try:
                # Check for cumulative columns: "Cum %Good", "Cum %Bad"
                if "Cum %Good" in woe_df.columns and "Cum %Bad" in woe_df.columns:
                    ks_vals[var] = float(
                        (woe_df["Cum %Good"] - woe_df["Cum %Bad"]).abs().max()
                    )
                elif "%Good" in woe_df.columns and "%Bad" in woe_df.columns:
                    # Fallback: per-bin KS = |%Good - %Bad|
                    ks_vals[var] = float(
                        (woe_df["%Good"] - woe_df["%Bad"]).abs().max()
                    )
            except Exception:
                ks_vals[var] = 0.0
        return pd.Series(ks_vals, name="KS")

    # ── Protocol methods ──

    def get_var_names(self) -> list[str]:
        return list(self._binner.varlist) if hasattr(self._binner, "varlist") else []

    def get_bins(self, var: str) -> pd.Series:
        if hasattr(self._binner, "bins"):
            return self._binner.bins.get(var, pd.Series([], name="bins"))
        return pd.Series([], name="bins")

    def get_woe_table(self, var: str) -> pd.DataFrame:
        if hasattr(self._binner, "woetables"):
            return self._binner.woetables.get(var, pd.DataFrame())
        return pd.DataFrame()

    def get_iv_table(self) -> pd.Series:
        if hasattr(self._binner, "ivtable"):
            return pd.Series(self._binner.ivtable)
        return pd.Series([], name="IV")

    def get_ks_table(self) -> pd.Series:
        return self._ks_table

    def get_model_summary(self) -> pd.DataFrame:
        if self._scorecard is not None:
            if hasattr(self._scorecard, "show_model_result"):
                return self._scorecard.show_model_result()
            if hasattr(self._scorecard, "model_result") and self._scorecard.model_result is not None:
                mr = self._scorecard.model_result
                return pd.DataFrame({
                    "Parameter": mr.params.index,
                    "Estimate": mr.params.values,
                    "Std-Error": mr.bse.values,
                    "Wald-Chi2": (mr.params / mr.bse) ** 2,
                })
        return pd.DataFrame()

    def get_scorecard(self) -> pd.DataFrame:
        if self._scorecard is not None and hasattr(self._scorecard, "score_card_result"):
            return self._scorecard.score_card_result
        return pd.DataFrame()

    def get_missing_dict(self) -> dict:
        if hasattr(self._binner, "missing_dict"):
            return dict(self._binner.missing_dict)
        return {}

    def get_dropped_vars(self) -> list[str]:
        dropped = []
        if hasattr(self._binner, "drops"):
            dropped.extend(list(self._binner.drops.keys()))
        if self._scorecard is not None and hasattr(self._scorecard, "dropped_vars"):
            dropped.extend(self._scorecard.dropped_vars)
        return list(set(dropped))
