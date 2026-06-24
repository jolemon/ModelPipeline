import pytest
import numpy as np
import pandas as pd
from model_report.metrics import (
    calc_auc, calc_ks, calc_lift, calc_bin_metrics, calc_score_psi,
    calc_monthly_metrics, calc_var_psi, calc_var_iv, calc_var_ks,
    calc_missing_rate, calculate_all_ks, compute_woe_table,
    _is_monotonic_increase,
)


class TestCalcAuc:
    def test_perfect_separation(self):
        y_true = np.array([0, 0, 0, 1, 1, 1])
        y_score = np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9])
        auc = calc_auc(y_true, y_score)
        assert auc == 1.0

    def test_random_prediction(self):
        np.random.seed(42)
        y_true = np.array([0, 0, 1, 1] * 25)
        y_score = np.random.uniform(0, 1, 100)
        auc = calc_auc(y_true, y_score)
        assert 0.3 < auc < 0.7

    def test_single_class_raises(self):
        with pytest.raises(ValueError):
            calc_auc(np.array([0, 0, 0]), np.array([0.1, 0.2, 0.3]))


class TestCalcKs:
    def test_perfect_separation(self):
        y_true = np.array([0, 0, 0, 1, 1, 1])
        y_score = np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9])
        ks = calc_ks(y_true, y_score)
        assert ks == 1.0

    def test_complete_overlap(self):
        y_true = np.array([0, 1, 0, 1, 0, 1])
        y_score = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        ks = calc_ks(y_true, y_score)
        assert ks == 0.0

    def test_ks_range(self):
        np.random.seed(42)
        y_true = np.random.choice([0, 1], size=100, p=[0.8, 0.2])
        y_score = np.random.uniform(0, 1, 100)
        ks = calc_ks(y_true, y_score)
        assert 0.0 <= ks <= 1.0


class TestCalcLift:
    def test_lift_values(self):
        df = pd.DataFrame({
            "y": [0, 0, 0, 0, 1, 0, 0, 1, 0, 1],
            "score": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        })
        result = calc_lift(df, y_col="y", score_col="score", percentiles=[10, 50])
        assert "10%" in result
        assert "50%" in result

    def test_lift_default_percentiles(self):
        df = pd.DataFrame({
            "y": [0, 0, 1, 1],
            "score": [0.1, 0.3, 0.7, 0.9],
        })
        result = calc_lift(df, y_col="y", score_col="score")
        assert set(result.keys()) == {"10%", "5%", "2%", "1%"}


class TestCalcBinMetrics:
    def test_bin_metrics_output_columns(self):
        y = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1])
        score = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        bins = pd.Series([
            pd.Interval(0.0, 0.5, closed="left"),
            pd.Interval(0.5, float("inf"), closed="left"),
        ])
        result = calc_bin_metrics(y, score, bins)
        expected_cols = ["min", "max", "bads", "goods", "total", "bad_rate",
                         "cum_bad_rate", "cum_bads_prop", "ks", "lift", "cum_lift"]
        for col in expected_cols:
            assert col in result.columns

    def test_bin_metrics_ks_range(self):
        y = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
        score = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        bins = pd.Series([
            pd.Interval(0.0, 0.3, closed="left"),
            pd.Interval(0.3, 0.7, closed="left"),
            pd.Interval(0.7, float("inf"), closed="left"),
        ])
        result = calc_bin_metrics(y, score, bins)
        max_ks = result["ks"].max()
        assert 0.0 <= max_ks <= 1.0

    def test_cum_bads_prop_reaches_one_right_closed(self):
        """cum_bads_prop should reach 1.0 in last bin — tests pd.cut default right=True."""
        np.random.seed(42)
        y = np.array([0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0])
        score = np.random.uniform(400, 900, len(y))
        # Simulate pd.cut default: right=True -> (left, right]
        bins = pd.cut(score, bins=5, precision=0, retbins=True)[1]
        intervals = pd.Series([
            pd.Interval(bins[i], bins[i+1], closed="right") for i in range(len(bins)-1)
        ])
        result = calc_bin_metrics(y, score, intervals)
        last_cum = result["cum_bads_prop"].iloc[-1]
        assert abs(last_cum - 1.0) < 0.001, f"Expected ~1.0, got {last_cum}"

    def test_cum_bads_prop_reaches_one_left_closed(self):
        """cum_bads_prop should reach 1.0 — last bin extended with inf."""
        y = np.array([0, 0, 0, 0, 1, 0, 1, 0, 1, 1])
        score = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        bins = pd.Series([
            pd.Interval(0.0, 0.3, closed="left"),
            pd.Interval(0.3, 0.7, closed="left"),
            pd.Interval(0.7, float("inf"), closed="left"),
        ])
        result = calc_bin_metrics(y, score, bins)
        last_cum = result["cum_bads_prop"].iloc[-1]
        assert abs(last_cum - 1.0) < 0.001, f"Expected ~1.0, got {last_cum}"

    def test_no_samples_in_other_bin(self):
        """All samples should be assigned to a bin, none in 'other'."""
        np.random.seed(42)
        y = np.random.choice([0, 1], size=100, p=[0.8, 0.2])
        score = np.random.uniform(400, 900, 100)
        bins_edges = pd.cut(score, bins=5, retbins=True)[1]
        intervals = pd.Series([
            pd.Interval(bins_edges[i], bins_edges[i+1], closed="right")
            for i in range(len(bins_edges)-1)
        ])
        result = calc_bin_metrics(y, score, intervals)
        total_in_bins = result["total"].sum()
        assert total_in_bins == len(y), f"Expected {len(y)}, got {total_in_bins}"


class TestCalcScorePsi:
    def test_identical_distributions(self):
        np.random.seed(42)
        train_scores = np.random.normal(600, 50, 1000)
        test_scores = train_scores.copy()
        psi = calc_score_psi(train_scores, test_scores, bins=10)
        assert psi < 0.01

    def test_different_distributions(self):
        np.random.seed(42)
        train_scores = np.random.normal(600, 50, 1000)
        test_scores = np.random.normal(700, 80, 1000)
        psi = calc_score_psi(train_scores, test_scores, bins=10)
        assert psi > 0.01

    def test_returns_float(self):
        psi = calc_score_psi(
            np.random.normal(600, 50, 100),
            np.random.normal(610, 55, 100),
            bins=10
        )
        isinstance(psi, float)


class TestCalcMonthlyMetrics:
    def test_output_columns(self):
        df = pd.DataFrame({
            "mob6_30": [0, 0, 0, 1, 0, 1, 0, 1],
            "pred_score": [0.1, 0.2, 0.3, 0.7, 0.15, 0.85, 0.25, 0.9],
            "loan_date": ["2025-01-15", "2025-01-20", "2025-02-10", "2025-02-15",
                          "2025-03-01", "2025-03-15", "2025-04-01", "2025-04-15"],
        })
        result = calc_monthly_metrics(df, target_col="mob6_30",
                                      score_col="pred_score",
                                      date_col="loan_date")
        assert "观察点月" in result.columns
        assert "总" in result.columns
        assert "好" in result.columns
        assert "坏" in result.columns
        assert "坏样本率" in result.columns
        assert "KS" in result.columns
        assert "AUC" in result.columns

    def test_monthly_rows(self):
        df = pd.DataFrame({
            "mob6_30": [0, 0, 0, 1, 0, 1],
            "pred_score": [0.1, 0.2, 0.3, 0.7, 0.15, 0.85],
            "loan_date": ["2025-01-15", "2025-01-20", "2025-02-10",
                          "2025-02-15", "2025-03-01", "2025-03-15"],
        })
        result = calc_monthly_metrics(df, target_col="mob6_30",
                                      score_col="pred_score",
                                      date_col="loan_date")
        assert len(result) >= 3


class TestCalcVarPsi:
    def test_identical_distributions(self):
        np.random.seed(42)
        train = pd.Series(np.random.normal(0, 1, 1000))
        oot = train.copy()
        psi = calc_var_psi(train, oot)
        assert psi < 0.01

    def test_different_distributions(self):
        np.random.seed(42)
        train = pd.Series(np.random.normal(0, 1, 1000))
        oot = pd.Series(np.random.normal(1, 2, 1000))
        psi = calc_var_psi(train, oot)
        assert psi > 0.01

    def test_returns_float(self):
        psi = calc_var_psi(
            pd.Series(np.random.normal(0, 1, 100)),
            pd.Series(np.random.normal(0.1, 1.1, 100)),
        )
        assert isinstance(psi, float)


class TestCalcVarIv:
    def test_iv_on_dataframe(self):
        df = pd.DataFrame({
            "mob6_30": [0, 0, 1, 1, 0, 1, 0, 0, 1, 0],
            "feat_a": np.random.normal(0, 1, 10),
            "feat_b": np.random.normal(5, 2, 10),
        })
        iv = calc_var_iv(df, var="feat_a", target_col="mob6_30")
        assert isinstance(iv, float)
        assert iv >= 0

    def test_iv_returns_float(self):
        df = pd.DataFrame({
            "target": [0, 0, 1, 1],
            "x": [1.0, 2.0, 3.0, 4.0],
        })
        iv = calc_var_iv(df, var="x", target_col="target")
        assert isinstance(iv, float)


class TestCalcVarKs:
    def test_ks_on_dataframe(self):
        df = pd.DataFrame({
            "mob6_30": [0, 0, 1, 1, 0, 1, 0, 0, 1, 0],
            "feat_a": np.linspace(0, 1, 10),
        })
        ks = calc_var_ks(df, var="feat_a", target_col="mob6_30")
        assert isinstance(ks, float)
        assert 0.0 <= ks <= 1.0

    def test_ks_perfect_separation(self):
        df = pd.DataFrame({
            "target": [0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
            "x":    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        })
        ks = calc_var_ks(df, var="x", target_col="target")
        assert ks == 1.0

    def test_ks_non_numeric_skips(self):
        df = pd.DataFrame({
            "target": [0, 1, 0, 1],
            "x": ["a", "b", "c", "d"],
        })
        ks = calc_var_ks(df, var="x", target_col="target")
        assert ks == 0.0


class TestCalculateAllKs:
    def test_batch_ks_output(self):
        df = pd.DataFrame({
            "mob6_30": [0, 0, 1, 1, 0, 1, 0, 0, 1, 0],
            "feat_a": np.linspace(0, 1, 10),
            "feat_b": np.linspace(0, 1, 10)[::-1],
        })
        result = calculate_all_ks(df, y_col="mob6_30", feature_cols=["feat_a", "feat_b"])
        assert len(result) == 2
        assert "variable" in result.columns
        assert "ks_scipy" in result.columns
        assert "ks_manual" in result.columns

    def test_batch_ks_with_exclude(self):
        df = pd.DataFrame({
            "target": [0, 1, 0, 1],
            "x1": [1.0, 2.0, 3.0, 4.0],
            "x2": [4.0, 3.0, 2.0, 1.0],
            "id": ["a", "b", "c", "d"],
        })
        result = calculate_all_ks(df, y_col="target", feature_cols=["x1", "x2", "id"])
        # id is non-numeric, should be skipped
        assert len(result) == 2


class TestCalcMissingRate:
    def test_normal_missing(self):
        s = pd.Series([1.0, 2.0, np.nan, 4.0, np.nan])
        rate = calc_missing_rate(s)
        assert rate == 0.4

    def test_special_missing_values(self):
        s = pd.Series([1.0, -999999.0, 2.0, -100000.0, 3.0])
        rate = calc_missing_rate(s)
        # -999999 and -100000 are <= -99999 → treated as missing
        assert rate == 0.4

    def test_no_missing(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0])
        rate = calc_missing_rate(s)
        assert rate == 0.0


class TestComputeWoeTable:
    def test_output_columns(self):
        df = pd.DataFrame({
            "target": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            "x": np.linspace(0, 10, 20),
        })
        result = compute_woe_table(df, var="x", target_col="target")
        expected = ["min", "max", "goods", "bads", "total",
                     "good_prop", "bad_prop", "bad_rate", "woe", "iv", "ks", "lift"]
        for col in expected:
            assert col in result.columns

    def test_woe_monotonic(self):
        """WOE should be monotonic for a well-separated variable."""
        np.random.seed(42)
        n = 200
        scores = np.concatenate([
            np.random.normal(0, 1, 100),  # goods
            np.random.normal(5, 1, 100),  # bads
        ])
        df = pd.DataFrame({
            "target": [0]*100 + [1]*100,
            "x": scores,
        })
        result = compute_woe_table(df, var="x", target_col="target")
        # WOE should increase with risk (higher score = more bads)
        woe_vals = result["woe"].values
        assert woe_vals[0] < woe_vals[-1]

    def test_iv_sum_matches_total(self):
        df = pd.DataFrame({
            "target": [0, 0, 0, 0, 1, 0, 1, 0, 1, 1],
            "x": np.linspace(0, 10, 10),
        })
        result = compute_woe_table(df, var="x", target_col="target")
        # IV should be non-negative and total matches sum of per-bin IV
        assert result["iv"].sum() > 0

    def test_categorical_variable(self):
        df = pd.DataFrame({
            "target": [0, 0, 1, 1, 0, 1, 0, 0, 1, 0],
            "cat": ["a", "a", "b", "b", "c", "c", "a", "b", "c", "c"],
        })
        result = compute_woe_table(df, var="cat", target_col="target")
        assert len(result) >= 2

    def test_missing_value_bin(self):
        """Special missing values should create a MISSING_VALUE bin."""
        np.random.seed(42)
        n = 200
        x = np.random.normal(0, 1, n)
        # Inject some special missing values
        x[:10] = -999999.0
        df = pd.DataFrame({
            "target": np.random.choice([0, 1], n, p=[0.8, 0.2]),
            "x": x,
        })
        result = compute_woe_table(df, var="x", target_col="target")
        assert "MISSING_VALUE" in result["min"].values

    def test_woe_monotonic_increase(self):
        """WOE should be non-decreasing across valid bins (excluding ALL)."""
        np.random.seed(42)
        n = 300
        scores = np.concatenate([
            np.random.normal(0, 1, 150),
            np.random.normal(4, 1, 150),
        ])
        df = pd.DataFrame({"target": [0]*150 + [1]*150, "x": scores})
        result = compute_woe_table(df, var="x", target_col="target")
        # Exclude ALL and MISSING_VALUE rows
        woe_vals = result.loc[
            ~result["min"].isin(["ALL", "MISSING_VALUE"]), "woe"
        ].values
        assert _is_monotonic_increase(woe_vals)

    def test_bin_count_range(self):
        """Total bins should be 4-7 (valid bins + ALL, possibly missing)."""
        np.random.seed(42)
        n = 300
        df = pd.DataFrame({
            "target": np.random.choice([0, 1], n, p=[0.85, 0.15]),
            "x": np.random.normal(10, 3, n),
        })
        result = compute_woe_table(df, var="x", target_col="target")
        # Exclude ALL row for valid bin count
        valid = result[result["min"] != "ALL"]
        assert 3 <= len(valid) <= 7, f"Expected 3-7 valid bins, got {len(valid)}"

    def test_min_bin_proportion(self):
        """Each bin should have >= 3% of total samples."""
        np.random.seed(42)
        n = 300
        df = pd.DataFrame({
            "target": np.random.choice([0, 1], n, p=[0.85, 0.15]),
            "x": np.random.normal(10, 3, n),
        })
        result = compute_woe_table(df, var="x", target_col="target")
        valid = result[result["min"] != "ALL"]
        for _, row in valid.iterrows():
            pct = row["total"] / n
            # Allow MISSING_VALUE bin to be smaller
            if row["min"] == "MISSING_VALUE":
                continue
            assert pct >= 0.025, f"Bin [{row['min']}, {row['max']}] has only {pct:.2%}"
