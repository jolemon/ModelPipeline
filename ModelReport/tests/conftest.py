import pytest
import pandas as pd
import numpy as np
from pathlib import Path

TEST_CSV_PATH = Path(__file__).parent.parent / "test.csv"


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Load test.csv as the standard test dataset."""
    return pd.read_csv(TEST_CSV_PATH, sep="\t")


@pytest.fixture
def small_df() -> pd.DataFrame:
    """Synthetic small dataset with known properties for unit tests."""
    np.random.seed(42)
    n = 200
    df = pd.DataFrame({
        "part_id": ["202501"] * 100 + ["202502"] * 100,
        "cert_no": [f"id_{i}" for i in range(n)],
        "loan_date": ["2025-01-15"] * 100 + ["2025-02-15"] * 100,
        "mob6_30": [0] * 80 + [1] * 20 + [0] * 70 + [1] * 30,
        "data_flag": ["train"] * 120 + ["test"] * 40 + ["oot"] * 40,
        "pred_score": np.random.uniform(0, 1, n).tolist(),
        "scorecard_score": np.random.randint(400, 900, n).astype(float).tolist(),
        "feat_a": np.random.normal(0, 1, n).tolist(),
        "feat_b": np.random.normal(5, 2, n).tolist(),
        "feat_c": np.random.exponential(1, n).tolist(),
    })
    return df


@pytest.fixture
def mock_scorecard():
    """Mock ScorecardProtocol for testing sheet builders."""
    from unittest.mock import MagicMock
    import pandas as pd
    import numpy as np

    sc = MagicMock()
    sc.get_var_names.return_value = ["feat_a", "feat_b", "feat_c"]
    sc.get_iv_table.return_value = pd.Series(
        [0.52, 0.31, 0.18], index=["feat_a", "feat_b", "feat_c"]
    )
    sc.get_ks_table.return_value = pd.Series(
        [0.42, 0.28, 0.15], index=["feat_a", "feat_b", "feat_c"]
    )
    sc.get_dropped_vars.return_value = []

    # Mock woe table for each variable
    def make_woe_table():
        df = pd.DataFrame({
            "min": [-np.inf, 0.0, 2.0],
            "max": [0.0, 2.0, np.inf],
            "Good": [60, 40, 20],
            "Bad": [10, 20, 40],
            "Total": [70, 60, 60],
            "%Good": [0.50, 0.33, 0.17],
            "%Bad": [0.14, 0.29, 0.57],
            "%Total": [0.37, 0.32, 0.32],
            "WoE": [1.27, 0.14, -1.21],
            "IV": [0.45, 0.03, 0.48],
            "Bad Rate": [0.14, 0.33, 0.67],
            "Lift": [0.35, 0.82, 1.67],
        })
        return df

    woe_tab = make_woe_table()
    sc.get_woe_table.return_value = woe_tab

    sc.get_bins.return_value = pd.Series(
        [pd.Interval(-np.inf, 0.0), pd.Interval(0.0, 2.0), pd.Interval(2.0, np.inf)],
        name="bins",
    )

    sc.get_model_summary.return_value = pd.DataFrame({
        "Parameter": ["intercept", "feat_a", "feat_b"],
        "Estimate": [-2.5, 0.85, -0.62],
        "Std-Error": [0.12, 0.08, 0.11],
        "Wald-Chi2": [434.0, 112.9, 31.8],
        "P-value": ["<.0001", "<.0001", "<.0001"],
        "P-value-num": [0.0, 0.0, 1.7e-8],
        "Std": [0.0, 0.89, 0.54],
        "Std-Estimate": [0.0, 0.41, -0.18],
        "VIF": [1.29, 1.10, 1.06],
    })

    sc.get_scorecard.return_value = pd.DataFrame({
        "name": ["feat_a", "feat_a", "feat_a", "feat_b", "feat_b", "feat_b"],
        "left": [-np.inf, 0.0, 2.0, -np.inf, 0.0, 2.0],
        "right": [0.0, 2.0, np.inf, 0.0, 2.0, np.inf],
        "score": [25, 15, 5, 30, 20, 10],
    }).set_index("name")

    sc.get_missing_dict.return_value = {}
    return sc
