import pytest
import numpy as np
import pandas as pd
from model_report.metrics import calc_auc, calc_ks, calc_lift, calc_bin_metrics, calc_score_psi, calc_monthly_metrics


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
            pd.Interval(0.5, 1.0, closed="left"),
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
            pd.Interval(0.7, 1.0, closed="left"),
        ])
        result = calc_bin_metrics(y, score, bins)
        max_ks = result["ks"].max()
        assert 0.0 <= max_ks <= 1.0


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
