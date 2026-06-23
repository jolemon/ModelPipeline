import pytest
import pandas as pd
import numpy as np
import pickle
import tempfile
from pathlib import Path
from model_report.interface import ScorecardProtocol, PickledScorecardAdapter


# ── Fake classes (module-level, picklable) ──
class FakeBinner:
    pass


class FakeScorecard:
    @staticmethod
    def show_model_result():
        return pd.DataFrame({
            "Parameter": ["intercept", "feat_a", "feat_b"],
            "Estimate": [-4.48, -0.83, -0.79],
            "Std-Error": [0.055, 0.062, 0.081],
            "Wald-Chi2": [6660.0, 181.6, 94.6],
            "P-value": ["<.0001", "<.0001", "<.0001"],
            "P-value-num": [0.0, 0.0, 0.0],
            "Std": [0.0, 0.89, 0.48],
            "Std-Estimate": [0.0, -0.407, -0.207],
            "VIF": [1.29, 1.10, 1.06],
        })


# ── Helper: build a realistic Binner-like object ──
def make_fake_binner():
    """Create an object matching Binner structure from scorecard_jsb.py."""
    binner = FakeBinner()
    binner.varlist = ["feat_a", "feat_b", "feat_c"]
    binner.drops = {}
    binner.missing_dict = {"feat_a": -999999.0}
    binner.vardict = {"feat_a": "特征A", "feat_b": "特征B"}

    binner.bins = {
        "feat_a": pd.Series([
            pd.Interval(-np.inf, 0.0, closed="right"),
            pd.Interval(0.0, 2.0, closed="right"),
            pd.Interval(2.0, np.inf, closed="right"),
        ]),
        "feat_b": pd.Series([
            pd.Interval(-np.inf, 5.0, closed="right"),
            pd.Interval(5.0, np.inf, closed="right"),
        ]),
        "feat_c": pd.Series([
            pd.Interval(-np.inf, 3.0, closed="right"),
            pd.Interval(3.0, np.inf, closed="right"),
        ]),
    }

    def make_woe(g, b):
        df = pd.DataFrame({
            "Good": [g, g // 2], "Bad": [b, b * 2],
            "Total": [g + b, g // 2 + b * 2],
            "%Good": [g / (g + b), (g // 2) / (g // 2 + b * 2)],
            "%Bad": [b / (g + b), (b * 2) / (g // 2 + b * 2)],
            "%Total": [0.6, 0.4],
            "WoE": [np.log(b / g), np.log(b * 2 / (g // 2))],
            "IV": [0.15, 0.08],
            "Bad Rate": [b / (g + b), b * 2 / (g // 2 + b * 2)],
            "Lift": [0.8, 1.5],
        })
        return df

    binner.woetables = {
        "feat_a": make_woe(1000, 200),
        "feat_b": make_woe(800, 100),
        "feat_c": make_woe(500, 50),
    }
    binner.ivtable = pd.Series([0.45, 0.32, 0.18], index=["feat_a", "feat_b", "feat_c"])
    return binner


def make_fake_scorecard(binner):
    """Create an object matching Scorecard structure from scorecard_jsb.py."""
    sc = FakeScorecard()
    sc.binner = binner
    sc.model_vars = ["feat_a", "feat_b"]
    sc.dropped_vars = ["feat_c"]
    sc.model_result = None
    sc.model_scorecard = None
    sc.show_model_result = FakeScorecard.show_model_result

    sc.score_card_result = pd.DataFrame({
        "name": ["feat_a", "feat_a", "feat_a", "feat_b", "feat_b"],
        "left": [-np.inf, 0.0, 2.0, -np.inf, 5.0],
        "right": [0.0, 2.0, np.inf, 5.0, np.inf],
        "score": [25, 15, 5, 30, 18],
    }).set_index("name")
    return sc


# ── Tests ──
class TestPickledScorecardAdapter:
    def test_adapter_from_scorecard_object(self):
        """Adapter extracts data from Scorecard → Binner hierarchy."""
        binner = make_fake_binner()
        scorecard = make_fake_scorecard(binner)
        adapter = PickledScorecardAdapter._from_object(scorecard)

        assert adapter.get_var_names() == ["feat_a", "feat_b", "feat_c"]
        assert len(adapter.get_iv_table()) == 3
        assert adapter.get_iv_table()["feat_a"] == 0.45
        assert "intercept" in adapter.get_model_summary()["Parameter"].values

    def test_adapter_from_binner_only(self):
        """Adapter works with just a Binner (no Scorecard)."""
        binner = make_fake_binner()
        adapter = PickledScorecardAdapter._from_object(binner)

        assert adapter.get_var_names() == ["feat_a", "feat_b", "feat_c"]
        assert len(adapter.get_bins("feat_a")) == 3
        # No scorecard → model summary is empty
        assert adapter.get_model_summary().empty
        assert adapter.get_scorecard().empty

    def test_get_woe_table(self):
        binner = make_fake_binner()
        scorecard = make_fake_scorecard(binner)
        adapter = PickledScorecardAdapter._from_object(scorecard)

        woe = adapter.get_woe_table("feat_a")
        assert not woe.empty
        assert "WoE" in woe.columns or "woe" in woe.columns

    def test_get_ks_table_from_woe(self):
        """KS values are extracted from WOE tables (Binner has no ks_table)."""
        binner = make_fake_binner()
        adapter = PickledScorecardAdapter._from_object(binner)

        ks = adapter.get_ks_table()
        assert isinstance(ks, pd.Series)
        assert len(ks) == 3

    def test_get_missing_dict(self):
        binner = make_fake_binner()
        adapter = PickledScorecardAdapter._from_object(binner)

        md = adapter.get_missing_dict()
        assert md["feat_a"] == -999999.0

    def test_get_dropped_vars(self):
        binner = make_fake_binner()
        scorecard = make_fake_scorecard(binner)
        adapter = PickledScorecardAdapter._from_object(scorecard)

        dropped = adapter.get_dropped_vars()
        assert "feat_c" in dropped

    def test_pickle_roundtrip(self):
        """Adapter works after pickle roundtrip of a Scorecard."""
        binner = FakeBinner()
        binner.varlist = ["feat_a", "feat_b"]
        binner.drops = {}
        binner.missing_dict = {}
        binner.vardict = {}
        binner.bins = {}
        binner.woetables = {}
        binner.ivtable = pd.Series([0.45, 0.32], index=["feat_a", "feat_b"])

        sc = FakeScorecard()
        sc.binner = binner
        sc.model_vars = ["feat_a", "feat_b"]
        sc.dropped_vars = []
        sc.model_result = None
        sc.score_card_result = pd.DataFrame()
        sc.show_model_result = FakeScorecard.show_model_result

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            pickle.dump(sc, f)
            pkl_path = f.name

        try:
            adapter = PickledScorecardAdapter(pkl_path)
            assert adapter.get_var_names() == ["feat_a", "feat_b"]
            assert "feat_a" in adapter.get_iv_table().index
            summary = adapter.get_model_summary()
            assert "intercept" in summary["Parameter"].values
        finally:
            Path(pkl_path).unlink()

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            PickledScorecardAdapter("nonexistent.pkl")

    def test_invalid_pkl_raises(self):
        """Non-scorecard pkl should raise clear error."""
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            pickle.dump({"not": "a scorecard"}, f)
            pkl_path = f.name

        try:
            with pytest.raises(ValueError, match="Scorecard"):
                PickledScorecardAdapter(pkl_path)
        finally:
            Path(pkl_path).unlink()
