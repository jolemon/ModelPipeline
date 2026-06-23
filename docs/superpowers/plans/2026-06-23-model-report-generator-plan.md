# Model Report Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a credit risk model report generator that consumes a trained scorecard + scoring data, outputs a multi-sheet Excel report per readme.md spec.

**Architecture:** Modular package `model_report/` with protocol-based scorecard abstraction. Three independent sheet builder modules produce structured DataFrames. ReportGenerator orchestrates, ExcelWriter handles formatting. CLI via click.

**Tech Stack:** Python 3.10+, pandas, numpy, scipy, scikit-learn, toad, openpyxl, click, pytest

**Development Mode:** TDD — every task writes tests first, verifies failure, then implements.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `model_report/__init__.py`
- Create: `requirements.txt`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create package structure and requirements**

```bash
mkdir -p model_report/sheets tests
touch model_report/__init__.py
touch model_report/sheets/__init__.py
touch tests/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

```text
pandas>=1.5.0
numpy>=1.24.0
scipy>=1.10.0
scikit-learn>=1.2.0
toad>=0.1.0
openpyxl>=3.1.0
click>=8.1.0
pytest>=7.4.0
```

- [ ] **Step 3: Write minimal __init__.py with version**

```python
# model_report/__init__.py
__version__ = "0.1.0"
```

- [ ] **Step 4: Commit**

```bash
git add model_report/ tests/ requirements.txt
git commit -m "chore: scaffold project structure"
```

---

### Task 2: Test Fixtures (conftest.py)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write conftest.py with fixtures**

```python
# tests/conftest.py
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

TEST_CSV_PATH = Path(__file__).parent.parent / "test.csv"


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Load test.csv as the standard test dataset."""
    df = pd.read_csv(TEST_CSV_PATH, sep="\t" if TEST_CSV_PATH.suffix == ".csv" else None)
    return df


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
        df.index = pd.IntervalIndex.from_arrays(
            [-np.inf, 0.0, 2.0], [0.0, 2.0, np.inf], closed="left"
        )
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
```

- [ ] **Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared fixtures"
```

---

### Task 3: ReportConfig

**Files:**
- Create: `model_report/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for ReportConfig**

```python
# tests/test_config.py
import pytest
from model_report.config import ReportConfig


class TestReportConfig:
    def test_default_values(self):
        cfg = ReportConfig()
        assert cfg.partition_col == "part_id"
        assert cfg.target_col == "mob6_30"
        assert cfg.flag_col == "data_flag"
        assert cfg.score_col == "pred_score"
        assert cfg.sc_score_col == "scorecard_score"
        assert cfg.top_n_vars == 10

    def test_custom_override(self):
        cfg = ReportConfig(target_col="target_mob6_30", top_n_vars=5)
        assert cfg.target_col == "target_mob6_30"
        assert cfg.top_n_vars == 5
        # unchanged defaults
        assert cfg.partition_col == "part_id"

    def test_flag_labels(self):
        cfg = ReportConfig()
        assert cfg.flag_labels == {
            "train": "训练集",
            "test": "测试集",
            "oot": "跨时间验证集",
            "oos": "压测",
        }

    def test_non_variable_columns(self):
        """Columns that should be excluded from variable analysis."""
        cfg = ReportConfig()
        non_vars = cfg.get_non_variable_columns()
        for col in ["part_id", "cert_no", "loan_date", "mob6_30", "data_flag",
                     "pred_score", "scorecard_score"]:
            assert col in non_vars
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_config.py -v
# Expected: ModuleNotFoundError or ImportError
```

- [ ] **Step 3: Implement ReportConfig**

```python
# model_report/config.py
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
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_config.py -v
# Expected: 4 passed
```

- [ ] **Step 5: Commit**

```bash
git add model_report/config.py tests/test_config.py
git commit -m "feat: add ReportConfig with defaults and column mapping"
```

---

### Task 4: Metrics — calc_auc and calc_ks

**Files:**
- Create: `model_report/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write failing tests for auc and ks**

```python
# tests/test_metrics.py
import pytest
import numpy as np
import pandas as pd
from model_report.metrics import calc_auc, calc_ks


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
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_metrics.py::TestCalcAuc tests/test_metrics.py::TestCalcKs -v
# Expected: ImportError
```

- [ ] **Step 3: Implement calc_auc and calc_ks**

```python
# model_report/metrics.py
import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve


def calc_auc(y_true, y_score) -> float:
    """Calculate AUC from true labels and predicted scores."""
    unique_labels = np.unique(y_true)
    if len(unique_labels) < 2:
        raise ValueError("y_true must contain both positive and negative samples for AUC")
    return float(roc_auc_score(y_true, y_score))


def calc_ks(y_true, y_score) -> float:
    """Calculate KS statistic from true labels and predicted scores."""
    fpr, tpr, _ = roc_curve(y_true, y_score)
    return float(np.max(tpr - fpr))
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_metrics.py::TestCalcAuc tests/test_metrics.py::TestCalcKs -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add model_report/metrics.py tests/test_metrics.py
git commit -m "feat: add calc_auc and calc_ks"
```

---

### Task 5: Metrics — calc_lift and calc_bin_metrics

**Files:**
- Modify: `model_report/metrics.py`
- Modify: `tests/test_metrics.py`

- [ ] **Step 1: Write failing tests for calc_lift and calc_bin_metrics**

Append to `tests/test_metrics.py`:

```python
from model_report.metrics import calc_lift, calc_bin_metrics


class TestCalcLift:
    def test_lift_values(self):
        df = pd.DataFrame({
            "y": [0, 0, 0, 0, 1, 0, 0, 1, 0, 1],  # 30% bad overall
            "score": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        })
        result = calc_lift(df, y_col="y", score_col="score", percentiles=[10, 50])
        assert "10%" in result
        assert "50%" in result
        # Top 10% (1 sample, score=1.0) is bad → lift > 1
        assert float(result["10%"]) > 1.0

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
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_metrics.py::TestCalcLift tests/test_metrics.py::TestCalcBinMetrics -v
# Expected: ImportError for calc_lift, calc_bin_metrics
```

- [ ] **Step 3: Implement calc_lift and calc_bin_metrics**

Append to `model_report/metrics.py`:

```python
import pandas as pd


def calc_lift(df: pd.DataFrame, y_col: str = "y", score_col: str = "score",
              percentiles: list = None, lower_is_riskier: bool = True) -> dict:
    """Calculate Lift values at given percentiles.

    Args:
        df: DataFrame with target and score columns.
        y_col: Target column name (1 = bad).
        score_col: Score column name.
        percentiles: List of percent thresholds, defaults to [10, 5, 2, 1].
        lower_is_riskier: If True, lower score means higher risk.

    Returns:
        dict mapping percentile string to lift value string (2 decimal places).
    """
    if percentiles is None:
        percentiles = [10, 5, 2, 1]

    ascending = lower_is_riskier
    df_sorted = df.sort_values(by=score_col, ascending=ascending).reset_index(drop=True)
    overall_bad_rate = df_sorted[y_col].mean()

    if overall_bad_rate == 0:
        return {f"{p}%": "0.00" for p in percentiles}

    lift_results = {}
    for p in percentiles:
        n = int(len(df_sorted) * p / 100)
        if n == 0:
            lift_results[f"{p}%"] = "0.00"
        else:
            top_bad_rate = df_sorted.iloc[:n][y_col].mean()
            lift = top_bad_rate / overall_bad_rate
            lift_results[f"{p}%"] = f"{lift:.2f}"

    return lift_results


def calc_bin_metrics(y_true, y_score, bins: pd.Series) -> pd.DataFrame:
    """Calculate per-bin performance metrics.

    Adapted from model_library/model_learn.py detailed_val_report.

    Args:
        y_true: Array-like of binary target labels.
        y_score: Array-like of predicted scores.
        bins: pd.Series of pd.Interval objects defining bin boundaries.

    Returns:
        DataFrame with columns: min, max, bads, goods, total, bad_rate,
        cum_bad_rate, cum_bads_prop, ks, lift, cum_lift.
    """
    base = pd.DataFrame({"score": y_score, "label": y_true})
    base["bin"] = _assign_bins(y_score, bins)

    total_bad = int(base["label"].sum())
    total_good = int((1 - base["label"]).sum())
    total_n = len(base)
    overall_bad_rate = total_bad / total_n if total_n > 0 else 0

    # Get unique bins in order
    unique_bins = bins.dropna().unique()
    sorted_bins = sorted(unique_bins, key=lambda x: x.left)

    rows = []
    cum_bad, cum_good = 0, 0
    for b in sorted_bins:
        mask = base["bin"] == str(b)
        seg_data = base[mask]
        bads = int(seg_data["label"].sum())
        goods = len(seg_data) - bads
        total = len(seg_data)

        if total == 0:
            continue

        cum_bad += bads
        cum_good += goods
        cum_total = cum_bad + cum_good

        bad_rate = bads / total
        cum_bad_rate = cum_bad / cum_total if cum_total > 0 else 0
        cum_bads_prop = cum_bad / total_bad if total_bad > 0 else 0
        ks = abs(cum_bad / total_bad - cum_good / total_good) if total_bad > 0 and total_good > 0 else 0
        lift = bad_rate / overall_bad_rate if overall_bad_rate > 0 else 0
        cum_lift = cum_bad_rate / overall_bad_rate if overall_bad_rate > 0 else 0

        rows.append({
            "min": b.left if b.left != float("-inf") else "-inf",
            "max": b.right if b.right != float("inf") else "inf",
            "bads": bads,
            "goods": goods,
            "total": total,
            "bad_rate": round(bad_rate, 4),
            "cum_bad_rate": round(cum_bad_rate, 4),
            "cum_bads_prop": round(cum_bads_prop, 4),
            "ks": round(ks, 4),
            "lift": round(lift, 4),
            "cum_lift": round(cum_lift, 4),
        })

    return pd.DataFrame(rows)


def _assign_bins(y_score, bins: pd.Series):
    """Assign each score to its bin interval string."""
    bin_list = bins.dropna().tolist()
    result = np.empty(len(y_score), dtype=object)
    result[:] = "other"
    for b in bin_list:
        mask = (y_score >= b.left) & (y_score < b.right)
        result[mask] = str(b)
    return result
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_metrics.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add model_report/metrics.py tests/test_metrics.py
git commit -m "feat: add calc_lift and calc_bin_metrics"
```

---

### Task 6: Metrics — calc_score_psi and calc_monthly_metrics

**Files:**
- Modify: `model_report/metrics.py`
- Modify: `tests/test_metrics.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_metrics.py`:

```python
from model_report.metrics import calc_score_psi, calc_monthly_metrics


class TestCalcScorePsi:
    def test_identical_distributions(self):
        np.random.seed(42)
        train_scores = np.random.normal(600, 50, 1000)
        test_scores = train_scores.copy()  # identical
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
        assert isinstance(psi, float)


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
        # Should have 3 months + 1 'all' row = 4
        assert len(result) >= 3
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_metrics.py::TestCalcScorePsi tests/test_metrics.py::TestCalcMonthlyMetrics -v
# Expected: ImportError
```

- [ ] **Step 3: Implement calc_score_psi and calc_monthly_metrics**

Append to `model_report/metrics.py`:

```python
def calc_score_psi(expected_scores, actual_scores, bins: int = 10) -> float:
    """Calculate PSI between two score distributions using equal-width binning.

    Args:
        expected_scores: Array-like of training/expected scores.
        actual_scores: Array-like of validation/actual scores.
        bins: Number of equal-width bins.

    Returns:
        PSI value as float.
    """
    expected = np.array(expected_scores)
    actual = np.array(actual_scores)

    min_val = min(expected.min(), actual.min())
    max_val = max(expected.max(), actual.max())
    bin_edges = np.linspace(min_val, max_val, bins + 1)
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    expected_binned = pd.cut(expected, bins=bin_edges)
    actual_binned = pd.cut(actual, bins=bin_edges)

    expected_dist = expected_binned.value_counts(normalize=True).sort_index()
    actual_dist = actual_binned.value_counts(normalize=True).sort_index()

    # Align distributions
    all_bins = expected_dist.index.union(actual_dist.index)
    expected_aligned = expected_dist.reindex(all_bins, fill_value=1e-10)
    actual_aligned = actual_dist.reindex(all_bins, fill_value=1e-10)

    psi = np.sum(
        (actual_aligned - expected_aligned) *
        np.log(actual_aligned / expected_aligned)
    )
    return float(psi)


def calc_monthly_metrics(df: pd.DataFrame, target_col: str = "mob6_30",
                         score_col: str = "pred_score",
                         date_col: str = "loan_date") -> pd.DataFrame:
    """Calculate AUC/KS/badrate by month.

    Adapted from model_library/model_learn.py calc_auc_ks_by_month.

    Args:
        df: Input DataFrame.
        target_col: Target column name (0/1 binary).
        score_col: Predicted score column name.
        date_col: Date column name for monthly grouping.

    Returns:
        DataFrame with columns: 观察点月, 总, 好, 坏, 坏样本率, KS, AUC.
    """
    tmp = df.copy()
    tmp["loan_month"] = tmp[date_col].astype(str).str.replace("-", "")[0:6]

    rows = []
    months = sorted(tmp["loan_month"].unique())

    for m in months + ["all"]:
        if m == "all":
            m_data = tmp
        else:
            m_data = tmp[tmp["loan_month"] == m]

        if len(m_data) == 0:
            continue

        total = len(m_data)
        bad = int(m_data[target_col].sum())
        good = total - bad
        badrate = bad / total if total > 0 else 0

        try:
            auc = calc_auc(m_data[target_col], m_data[score_col])
            ks = calc_ks(m_data[target_col], m_data[score_col])
        except ValueError:
            auc = float("nan")
            ks = float("nan")

        rows.append({
            "观察点月": m,
            "总": total,
            "好": good,
            "坏": bad,
            "坏样本率": round(badrate, 4),
            "KS": round(ks, 4) if not np.isnan(ks) else ks,
            "AUC": round(auc, 4) if not np.isnan(auc) else auc,
        })

    return pd.DataFrame(rows).sort_values(by="观察点月", ascending=True)
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_metrics.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add model_report/metrics.py tests/test_metrics.py
git commit -m "feat: add calc_score_psi and calc_monthly_metrics"
```

---

### Task 7: ScorecardProtocol Interface

**Files:**
- Create: `model_report/interface.py`
- Create: `tests/test_interface.py`

- [ ] **Step 1: Write failing tests for ScorecardProtocol and PickledScorecardAdapter**

```python
# tests/test_interface.py
import pytest
import pandas as pd
import numpy as np
from model_report.interface import ScorecardProtocol, PickledScorecardAdapter


class TestPickledScorecardAdapter:
    def test_adapter_creates_from_mock(self, mock_scorecard):
        """Verify adapter can wrap any object that matches protocol."""
        # We test the structural interface, not the Protocol itself
        assert hasattr(mock_scorecard, "get_var_names")
        assert hasattr(mock_scorecard, "get_woe_table")
        assert hasattr(mock_scorecard, "get_iv_table")
        assert hasattr(mock_scorecard, "get_model_summary")
        assert hasattr(mock_scorecard, "get_scorecard")

    def test_adapter_not_implemented(self):
        """PickledScorecardAdapter requires actual .pkl file, test error."""
        with pytest.raises(FileNotFoundError):
            PickledScorecardAdapter("nonexistent_file.pkl")
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_interface.py -v
# Expected: ImportError
```

- [ ] **Step 3: Implement ScorecardProtocol and PickledScorecardAdapter**

```python
# model_report/interface.py
from typing import Protocol, runtime_checkable
import pandas as pd
import pickle


@runtime_checkable
class ScorecardProtocol(Protocol):
    """Protocol defining the interface report generator expects from a scorecard.

    Any object that satisfies this protocol can be used with ReportGenerator.
    """

    def get_var_names(self) -> list[str]:
        """Return list of all variable names."""
        ...

    def get_bins(self, var: str) -> pd.Series:
        """Return bin intervals for a variable."""
        ...

    def get_woe_table(self, var: str) -> pd.DataFrame:
        """Return WOE table DataFrame for a variable (with WoE, IV, KS, Lift columns)."""
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

    def _require_attr(self, name: str):
        if not hasattr(self._scorecard, name):
            raise AttributeError(
                f"Loaded scorecard object has no attribute '{name}'. "
                f"It must implement ScorecardProtocol."
            )

    def get_var_names(self) -> list[str]:
        self._require_attr("varlist")
        return list(self._scorecard.varlist)

    def get_bins(self, var: str) -> pd.Series:
        self._require_attr("bins")
        return self._scorecard.bins.get(var, pd.Series([], name="bins"))

    def get_woe_table(self, var: str) -> pd.DataFrame:
        self._require_attr("woetables")
        return self._scorecard.woetables.get(var, pd.DataFrame())

    def get_iv_table(self) -> pd.Series:
        self._require_attr("ivtable")
        return self._scorecard.ivtable

    def get_ks_table(self) -> pd.Series:
        self._require_attr("ks_table")
        if hasattr(self._scorecard, "ks_table"):
            return self._scorecard.ks_table
        return pd.Series([], name="KS")

    def get_model_summary(self) -> pd.DataFrame:
        self._require_attr("show_model_result")
        return self._scorecard.show_model_result()

    def get_scorecard(self) -> pd.DataFrame:
        self._require_attr("score_card_result")
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
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_interface.py -v
# Expected: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add model_report/interface.py tests/test_interface.py
git commit -m "feat: add ScorecardProtocol and PickledScorecardAdapter"
```

---

### Task 8: Metadata Loader

**Files:**
- Create: `model_report/metadata.py`
- Create: `tests/test_metadata.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_metadata.py
import pytest
import tempfile
from pathlib import Path
from model_report.metadata import load_variable_metadata


class TestLoadVariableMetadata:
    def test_load_csv_metadata(self):
        csv_content = "变量名,变量解释含义,来源,表描述\nfeat_a,近3个月消费笔数,wdyy.table_a,消费状态\nfeat_b,近24个月余额,wdyy.table_b,额度状态\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            tmp_path = f.name

        try:
            result = load_variable_metadata(tmp_path)
            assert result["feat_a"]["变量解释含义"] == "近3个月消费笔数"
            assert result["feat_a"]["来源"] == "wdyy.table_a"
            assert result["feat_b"]["表描述"] == "额度状态"
        finally:
            Path(tmp_path).unlink()

    def test_missing_file_returns_empty(self):
        result = load_variable_metadata("nonexistent.csv")
        assert result == {}

    def test_no_metadata_returns_empty_strings(self):
        result = load_variable_metadata(None)
        assert result == {}
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_metadata.py -v
# Expected: ImportError
```

- [ ] **Step 3: Implement load_variable_metadata**

```python
# model_report/metadata.py
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


def load_variable_metadata(path: str | None) -> dict:
    """Load variable metadata from CSV/YAML file.

    Expected CSV columns: 变量名, 变量解释含义, 来源, 表描述

    Returns:
        dict mapping variable name → dict of metadata fields.
        Returns empty dict if file not found or path is None.
    """
    if path is None:
        return {}

    file_path = Path(path)
    if not file_path.exists():
        logger.warning(f"Variable metadata file not found: {path}, "
                       "filling metadata columns with empty strings.")
        return {}

    try:
        if file_path.suffix in (".csv",):
            df = pd.read_csv(path)
        elif file_path.suffix in (".yaml", ".yml"):
            import yaml
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            df = pd.DataFrame(data)
        elif file_path.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            logger.warning(f"Unsupported metadata format: {file_path.suffix}")
            return {}

        # Standardize: use first column as variable name key
        key_col = df.columns[0]
        df = df.set_index(key_col)
        return df.to_dict(orient="index")

    except Exception as e:
        logger.warning(f"Failed to load metadata from {path}: {e}")
        return {}
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_metadata.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add model_report/metadata.py tests/test_metadata.py
git commit -m "feat: add variable metadata loader"
```

---

### Task 9: Sheet 1 — Model Design

**Files:**
- Create: `model_report/sheets/model_design.py`
- Create: `tests/test_model_design.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_model_design.py
import pytest
import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.sheets.model_design import build_model_design_sheet


class TestBuildModelDesignSheet:
    def test_returns_two_dataframes(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        assert "partition_distribution" in result
        assert "modeling_score" in result

    def test_partition_distribution_columns(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        df = result["partition_distribution"]
        expected_cols = ["样本数据集划分标签", "样本分区", "好", "坏", "总数", "坏占比"]
        for col in expected_cols:
            assert col in df.columns

    def test_partition_distribution_has_total_row(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        df = result["partition_distribution"]
        assert "总计" in df["样本数据集划分标签"].values

    def test_modeling_score_fixed_rows(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        df = result["modeling_score"]
        labels = df["样本数据集划分标签"].tolist()
        assert "训练集" in labels
        assert "测试集" in labels
        assert "跨时间验证集" in labels
        assert "总计" in labels

    def test_bad_rate_format(self, small_df):
        config = ReportConfig()
        result = build_model_design_sheet(small_df, config)
        df = result["partition_distribution"]
        bad_rate_val = df.loc[df["样本数据集划分标签"] != "总计", "坏占比"].iloc[0]
        # Should be a formatted string like "1.49%"
        assert isinstance(bad_rate_val, str)
        assert "%" in bad_rate_val
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_model_design.py -v
# Expected: ImportError
```

- [ ] **Step 3: Implement build_model_design_sheet**

```python
# model_report/sheets/model_design.py
import pandas as pd
from model_report.config import ReportConfig


def build_model_design_sheet(data: pd.DataFrame, config: ReportConfig) -> dict:
    """Build Sheet 1: Model Design.

    Produces:
        1.1 partition_distribution — breakdown by data_flag × partition
        1.2 modeling_score — train/test/oot summary
    """
    df = data.copy()

    # 1.1 Partition distribution
    part_dist = _build_partition_distribution(df, config)

    # 1.2 Modeling score summary
    score_summary = _build_modeling_score(df, config)

    return {
        "partition_distribution": part_dist,
        "modeling_score": score_summary,
    }


def _build_partition_distribution(df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
    """Build partition distribution table."""
    flag_col = config.flag_col
    part_col = config.partition_col
    target_col = config.target_col

    flag_labels = config.flag_labels

    rows = []
    # Sort partitions naturally
    partitions = sorted(df[part_col].astype(str).unique())

    for part in partitions:
        for flag in ["train", "test", "oot", "oos"]:
            subset = df[(df[part_col].astype(str) == part) & (df[flag_col] == flag)]
            if len(subset) == 0:
                continue
            bad = int(subset[target_col].sum())
            total = len(subset)
            good = total - bad
            bad_rate = bad / total if total > 0 else 0
            rows.append({
                "样本数据集划分标签": flag_labels.get(flag, flag),
                "样本分区": part,
                "好": good,
                "坏": bad,
                "总数": total,
                "坏占比": f"{bad_rate:.2%}",
            })

    # Total row
    total_bad = int(df[target_col].sum())
    total_count = len(df)
    total_good = total_count - total_bad
    rows.append({
        "样本数据集划分标签": "总计",
        "样本分区": "",
        "好": total_good,
        "坏": total_bad,
        "总数": total_count,
        "坏占比": f"{total_bad / total_count:.2%}" if total_count > 0 else "0.00%",
    })

    return pd.DataFrame(rows)


def _build_modeling_score(df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
    """Build modeling score summary (train/test/oot/total)."""
    flag_col = config.flag_col
    target_col = config.target_col

    flag_labels = config.flag_labels

    rows = []
    for flag in ["train", "test", "oot"]:
        subset = df[df[flag_col] == flag]
        bad = int(subset[target_col].sum())
        total = len(subset)
        good = total - bad
        bad_rate = bad / total if total > 0 else 0
        rows.append({
            "样本数据集划分标签": flag_labels.get(flag, flag),
            "好": good,
            "坏": bad,
            "总数": total,
            "坏占比": f"{bad_rate:.2%}",
        })

    # Total
    total_bad = int(df[target_col].sum())
    total_count = len(df)
    total_good = total_count - total_bad
    rows.append({
        "样本数据集划分标签": "总计",
        "好": total_good,
        "坏": total_bad,
        "总数": total_count,
        "坏占比": f"{total_bad / total_count:.2%}" if total_count > 0 else "0.00%",
    })

    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_model_design.py -v
# Expected: 5 passed
```

- [ ] **Step 5: Commit**

```bash
git add model_report/sheets/model_design.py tests/test_model_design.py
git commit -m "feat: add Sheet 1 - model design builder"
```

---

### Task 10: ExcelWriter

**Files:**
- Create: `model_report/writer.py`
- Create: `tests/test_writer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_writer.py
import pytest
import tempfile
import pandas as pd
from pathlib import Path
from model_report.writer import ExcelWriter
from model_report.config import ReportConfig


class TestExcelWriter:
    @pytest.fixture
    def writer(self):
        return ExcelWriter()

    @pytest.fixture
    def sample_data(self):
        return {
            "partition_distribution": pd.DataFrame({
                "样本数据集划分标签": ["训练集", "测试集", "总计"],
                "样本分区": ["202501", "202501", ""],
                "好": [80, 35, 115],
                "坏": [20, 5, 25],
                "总数": [100, 40, 140],
                "坏占比": ["20.00%", "12.50%", "17.86%"],
            }),
            "modeling_score": pd.DataFrame({
                "样本数据集划分标签": ["训练集", "测试集", "跨时间验证集", "总计"],
                "好": [80, 35, 38, 153],
                "坏": [20, 5, 2, 27],
                "总数": [100, 40, 40, 180],
                "坏占比": ["20.00%", "12.50%", "5.00%", "15.00%"],
            }),
        }

    def test_write_creates_file(self, writer, sample_data):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            writer.write(output_path, {"模型设计": sample_data})
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0
        finally:
            Path(output_path).unlink()

    def test_write_sheet_names(self, writer, sample_data):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            writer.write(output_path, {"模型设计": sample_data})
            import openpyxl
            wb = openpyxl.load_workbook(output_path)
            assert "模型设计" in wb.sheetnames
        finally:
            Path(output_path).unlink()
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_writer.py -v
# Expected: ImportError
```

- [ ] **Step 3: Implement ExcelWriter**

```python
# model_report/writer.py
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, numbers
from openpyxl.formatting.rule import DataBarRule
from openpyxl.utils import get_column_letter


class ExcelWriter:
    """Writes structured DataFrames to formatted Excel sheets."""

    HEADER_FONT = Font(bold=True, size=11)
    HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    HEADER_FONT_WHITE = Font(bold=True, size=11, color="FFFFFF")
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def write(self, output_path: str, sheets: dict) -> None:
        """Write structured data to Excel.

        Args:
            output_path: Path to output .xlsx file.
            sheets: dict mapping sheet_name → dict[str, DataFrame].
                    Each sheet dict has section names as keys and DataFrames as values.
        """
        wb = Workbook()
        wb.remove(wb.active)  # Remove default sheet

        for sheet_name, sections in sheets.items():
            ws = wb.create_sheet(title=sheet_name[:31])  # Excel 31-char sheet name limit
            current_row = 1

            for section_name, df in sections.items():
                if df is None or df.empty:
                    continue

                # Write section title
                ws.cell(row=current_row, column=1, value=section_name).font = Font(
                    bold=True, size=13
                )
                current_row += 1

                # Write headers
                for col_idx, col_name in enumerate(df.columns, 1):
                    cell = ws.cell(row=current_row, column=col_idx, value=str(col_name))
                    cell.font = self.HEADER_FONT_WHITE
                    cell.fill = self.HEADER_FILL
                    cell.alignment = self.HEADER_ALIGNMENT
                current_row += 1

                # Write data
                for _, row in df.iterrows():
                    for col_idx, value in enumerate(row, 1):
                        ws.cell(row=current_row, column=col_idx, value=value)
                    current_row += 1

                # Add spacing between sections
                current_row += 1

                # Auto-fit column widths
                self._auto_fit_columns(ws, df)

            # Apply data bar formatting to columns with rate/lift values
            self._apply_data_bars(ws, df)

    def _auto_fit_columns(self, ws, df: pd.DataFrame) -> None:
        """Set column widths based on content."""
        for col_idx, col_name in enumerate(df.columns, 1):
            max_width = max(
                len(str(col_name)),
                df[col_name].astype(str).str.len().max() if len(df) > 0 else 0,
            )
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_width + 4, 40)

    def _apply_data_bars(self, ws, df: pd.DataFrame) -> None:
        """Apply data bar conditional formatting to specific columns."""
        data_bar_cols = ["woe", "bad_rate", "lift", "cum_lift", "坏占比"]

        for col_idx, col_name in enumerate(df.columns, 1):
            col_lower = col_name.lower().replace(" ", "_")
            if any(pat in col_lower for pat in data_bar_cols):
                col_letter = get_column_letter(col_idx)
                data_start = 3  # After title + header
                data_end = len(df) + 2
                if data_end > data_start:
                    rule = DataBarRule(
                        start_type="min",
                        end_type="max",
                        color="5B9BD5",
                        showValue=True,
                    )
                    ws.conditional_formatting.add(
                        f"{col_letter}{data_start}:{col_letter}{data_end}", rule
                    )
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_writer.py -v
# Expected: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add model_report/writer.py tests/test_writer.py
git commit -m "feat: add ExcelWriter with formatting"
```

---

### Task 11: Sheet 2 — Variable Analysis

**Files:**
- Create: `model_report/sheets/variable_analysis.py`
- Create: `tests/test_variable_analysis.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_variable_analysis.py
import pytest
import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.sheets.variable_analysis import build_variable_analysis_sheet


class TestBuildVariableAnalysisSheet:
    def test_returns_two_sections(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        metadata = {"feat_a": {"变量解释含义": "test var a", "来源": "src_a", "表描述": "desc_a"}}
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, metadata)
        assert "ivar_ks_psi_overview" in result
        assert "top10_woe_bins" in result

    def test_overview_columns(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        metadata = {}
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, metadata)
        df = result["ivar_ks_psi_overview"]
        expected = ["序号", "变量名", "变量解释含义", "来源", "表描述", "数据类型"]
        for col in expected:
            assert col in df.columns

    def test_overview_iv_train_column(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        metadata = {}
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, metadata)
        df = result["ivar_ks_psi_overview"]
        assert "iv_train" in df.columns
        assert "iv_oot" in df.columns

    def test_overview_uses_metadata(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        metadata = {"feat_a": {"变量解释含义": "test meaning", "来源": "test_source", "表描述": "test_desc"}}
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, metadata)
        df = result["ivar_ks_psi_overview"]
        row = df[df["变量名"] == "feat_a"].iloc[0]
        assert row["变量解释含义"] == "test meaning"

    def test_overview_missing_metadata_fills_empty(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_variable_analysis_sheet(small_df, mock_scorecard, {}, config)
        df = result["ivar_ks_psi_overview"]
        row = df[df["变量名"] == "feat_a"].iloc[0]
        assert row["变量解释含义"] == ""

    def test_top10_woe_has_variables(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            score_col="pred_score",
            sc_score_col="scorecard_score",
            top_n_vars=3,
        )
        result = build_variable_analysis_sheet(small_df, mock_scorecard, config, {})
        top10 = result["top10_woe_bins"]
        # Should have at most top_n_vars entries, each a (var_name, DataFrame) tuple
        assert len(top10) <= 3
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_variable_analysis.py -v
# Expected: ImportError
```

- [ ] **Step 3: Implement build_variable_analysis_sheet**

```python
# model_report/sheets/variable_analysis.py
import pandas as pd
import numpy as np
from model_report.config import ReportConfig


def build_variable_analysis_sheet(
    data: pd.DataFrame,
    scorecard,
    config: ReportConfig,
    metadata: dict,
) -> dict:
    """Build Sheet 2: Variable Analysis.

    Produces:
        2.1 ivar_ks_psi_overview — all variables IV/KS/PSI table
        2.2 top10_woe_bins — list of (var_name, DataFrame) for top N variables WOE tables
    """
    feature_cols = config.get_feature_columns(list(data.columns))
    iv_table = scorecard.get_iv_table()
    ks_table = scorecard.get_ks_table()

    # 2.1 Variable overview
    overview = _build_variable_overview(data, feature_cols, iv_table, ks_table,
                                        scorecard, config, metadata)

    # 2.2 Top N WOE tables
    top_n = config.top_n_vars
    top_vars = overview.head(top_n)["变量名"].tolist()
    top10 = []
    for var in top_vars:
        woe_df = scorecard.get_woe_table(var)
        if woe_df is not None and not woe_df.empty:
            top10.append((var, _format_woe_table(woe_df)))

    return {
        "ivar_ks_psi_overview": overview,
        "top10_woe_bins": top10,
    }


def _build_variable_overview(
    data: pd.DataFrame,
    feature_cols: list,
    iv_table: pd.Series,
    ks_table: pd.Series,
    scorecard,
    config: ReportConfig,
    metadata: dict,
) -> pd.DataFrame:
    """Build the variable IV/KS/PSI overview table."""
    rows = []
    flag_col = config.flag_col

    train_data = data[data[flag_col] == "train"]
    oot_data = data[data[flag_col] == "oot"]

    for idx, var in enumerate(feature_cols, 1):
        var_meta = metadata.get(var, {})
        dtype = str(data[var].dtype)

        # Missing rate train
        missing_train = train_data[var].isna().mean() if len(train_data) > 0 else 0
        missing_oot = oot_data[var].isna().mean() if len(oot_data) > 0 else 0

        # IV
        iv_train = iv_table.get(var, np.nan) if isinstance(iv_table, pd.Series) else np.nan
        iv_oot_val = np.nan  # OOT IV computed separately if needed

        # KS
        ks_train = ks_table.get(var, np.nan) if isinstance(ks_table, pd.Series) else np.nan
        ks_oot_val = np.nan

        # PSI
        psi_val = np.nan

        rows.append({
            "序号": idx,
            "变量名": var,
            "变量解释含义": var_meta.get("变量解释含义", ""),
            "来源": var_meta.get("来源", ""),
            "表描述": var_meta.get("表描述", ""),
            "数据类型": dtype,
            "缺失率_train": f"{missing_train:.2%}",
            "缺失率_oot": f"{missing_oot:.2%}",
            "iv_train": round(iv_train, 2) if not np.isnan(iv_train) else "",
            "iv_oot": round(iv_oot_val, 2) if not np.isnan(iv_oot_val) else "",
            "ks_train": round(ks_train, 2) if not np.isnan(ks_train) else "",
            "ks_oot": round(ks_oot_val, 2) if not np.isnan(ks_oot_val) else "",
            "psi": round(psi_val, 4) if not np.isnan(psi_val) else "",
        })

    df = pd.DataFrame(rows)

    # Sort by IV descending
    df["_iv_sort"] = pd.to_numeric(df["iv_train"], errors="coerce")
    df = df.sort_values("_iv_sort", ascending=False).drop(columns=["_iv_sort"])
    df["序号"] = range(1, len(df) + 1)

    return df


def _format_woe_table(woe_df: pd.DataFrame) -> pd.DataFrame:
    """Format WOE table for Excel output — match readme.md spec column layout."""
    cols = ["min", "max", "goods", "bads", "total", "good_prop", "bad_prop",
            "bad_rate", "woe", "iv", "ks", "lift"]

    out = pd.DataFrame()
    for col in cols:
        col_map = {
            "min": "min",
            "max": "max",
            "Good": "goods",
            "Bad": "bads",
            "Total": "total",
            "%Good": "good_prop",
            "%Bad": "bad_prop",
            "Bad Rate": "bad_rate",
            "WoE": "woe",
            "IV": "iv",
            "Lift": "lift",
        }

        if col in woe_df.columns:
            out[col] = woe_df[col]
        elif col in col_map and col_map[col] is not None:
            src_col = [k for k, v in col_map.items() if v == col]
            if src_col and src_col[0] in woe_df.columns:
                out[col] = woe_df[src_col[0]]

    # Add ALL row
    # (the woe_df typically includes an 'All' row already)

    return out if not out.empty else woe_df
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_variable_analysis.py -v
# Expected: 6 passed
```

- [ ] **Step 5: Commit**

```bash
git add model_report/sheets/variable_analysis.py tests/test_variable_analysis.py
git commit -m "feat: add Sheet 2 - variable analysis builder"
```

---

### Task 12: Sheet 3 — Model Performance

**Files:**
- Create: `model_report/sheets/model_performance.py`
- Create: `tests/test_model_performance.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_model_performance.py
import pytest
import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.sheets.model_performance import build_model_performance_sheet


class TestBuildModelPerformanceSheet:
    def test_returns_all_sections(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        assert "scorecard_detail" in result
        assert "sample_effect" in result
        assert "backtest_effect" in result
        assert "bin_performance" in result

    def test_scorecard_detail_columns(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        df = result["scorecard_detail"]
        expected_cols = ["Parameter", "Estimate", "Std-Error", "Wald-Chi2",
                         "P-value", "P-value-num", "Std", "Std-Estimate", "VIF"]
        for col in expected_cols:
            assert col in df.columns

    def test_sample_effect_columns(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        df = result["sample_effect"]
        expected_cols = ["样本集", "观察点月", "样本标签", "总", "好", "坏", "坏占比", "KS", "AUC"]
        for col in expected_cols:
            assert col in df.columns

    def test_backtest_has_partition_rows(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        df = result["backtest_effect"]
        # Should have rows for each partition
        partitions = small_df["part_id"].unique()
        assert len(df) >= len(partitions)

    def test_bin_performance(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        result = build_model_performance_sheet(small_df, mock_scorecard, config)
        bin_perf = result["bin_performance"]
        # Should be a list of (partition_label, DataFrame) tuples
        assert len(bin_perf) > 0
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_model_performance.py -v
# Expected: ImportError
```

- [ ] **Step 3: Implement build_model_performance_sheet**

```python
# model_report/sheets/model_performance.py
import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.metrics import (
    calc_auc, calc_ks, calc_lift, calc_bin_metrics, calc_monthly_metrics
)


def build_model_performance_sheet(
    data: pd.DataFrame,
    scorecard,
    config: ReportConfig,
) -> dict:
    """Build Sheet 3: Model Performance.

    Produces:
        3.1 scorecard_detail — model coefficients table
        3.2 sample_effect — train/test/oot metrics
        3.3 backtest_effect — monthly breakdown by partition
        3.4 bin_performance — per-partition binning performance
    """
    # 3.1 Scorecard detail
    detail = scorecard.get_model_summary()

    # 3.2 Sample effect (train/test/oot)
    sample_effect = _build_sample_effect(data, config)

    # 3.3 Backtest effect (monthly)
    backtest = _build_backtest_effect(data, config)

    # 3.4 Bin performance per partition
    bin_perf = _build_bin_performance(data, config)

    return {
        "scorecard_detail": detail,
        "sample_effect": sample_effect,
        "backtest_effect": backtest,
        "bin_performance": bin_perf,
    }


def _build_sample_effect(df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
    """Build train/test/oot metrics table."""
    flag_col = config.flag_col
    target_col = config.target_col
    score_col = config.score_col
    flag_labels = config.flag_labels

    rows = []
    for flag in ["train", "test", "oot"]:
        subset = df[df[flag_col] == flag]
        if len(subset) == 0:
            continue

        total = len(subset)
        bad = int(subset[target_col].sum())
        good = total - bad
        bad_rate = bad / total if total > 0 else 0

        try:
            auc = calc_auc(subset[target_col], subset[score_col])
            ks = calc_ks(subset[target_col], subset[score_col])
            lift_vals = calc_lift(subset, y_col=target_col, score_col=score_col)
        except (ValueError, IndexError):
            auc = float("nan")
            ks = float("nan")
            lift_vals = {"10%": "", "5%": "", "2%": "", "1%": ""}

        rows.append({
            "样本集": flag_labels.get(flag, flag),
            "观察点月": _get_date_range(subset, config),
            "样本标签": config.target_label,
            "总": total,
            "好": good,
            "坏": bad,
            "坏占比": f"{bad_rate:.2%}",
            "KS": round(ks, 2) if not np.isnan(ks) else "",
            "AUC": round(auc, 2) if not np.isnan(auc) else "",
            "10%lift": lift_vals.get("10%", ""),
            "5%lift": lift_vals.get("5%", ""),
            "2%lift": lift_vals.get("2%", ""),
            "1%lift": lift_vals.get("1%", ""),
        })

    return pd.DataFrame(rows)


def _build_backtest_effect(df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
    """Build monthly backtest effect table."""
    target_col = config.target_col
    score_col = config.score_col
    date_col = config.date_col
    partition_col = config.partition_col
    flag_col = config.flag_col

    monthly = calc_monthly_metrics(df, target_col=target_col,
                                   score_col=score_col, date_col=date_col)

    rows = []
    for _, row in monthly.iterrows():
        month = row["观察点月"]
        if month == "all":
            continue

        month_data = df[df[date_col].astype(str).str.replace("-", "")[0:6] == month]

        # Determine if this month belongs to train/test or oot or oos
        flags_in_month = month_data[flag_col].unique()
        if "oot" in flags_in_month:
            partition_label = "跨时间验证集"
        elif "oos" in flags_in_month:
            partition_label = "压测"
        else:
            partition_label = "训练测试集"

        try:
            lift_vals = calc_lift(month_data, y_col=target_col, score_col=score_col)
        except (ValueError, IndexError):
            lift_vals = {"10%": "", "5%": "", "2%": "", "1%": ""}

        rows.append({
            "全量样本回溯": partition_label,
            "观察点月": month,
            "样本标签": config.target_label,
            "总": row["总"],
            "好": row["好"],
            "坏": row["坏"],
            "坏占比": f"{row['坏样本率']:.2%}",
            "KS": row["KS"] if not (isinstance(row["KS"], float) and np.isnan(row["KS"])) else "",
            "AUC": row["AUC"] if not (isinstance(row["AUC"], float) and np.isnan(row["AUC"])) else "",
            "10%lift": lift_vals.get("10%", ""),
            "5%lift": lift_vals.get("5%", ""),
            "2%lift": lift_vals.get("2%", ""),
            "1%lift": lift_vals.get("1%", ""),
        })

    # Total row
    total = len(df)
    total_bad = int(df[target_col].sum())
    total_good = total - total_bad
    try:
        total_auc = calc_auc(df[target_col], df[score_col])
        total_ks = calc_ks(df[target_col], df[score_col])
        total_lift = calc_lift(df, y_col=target_col, score_col=score_col)
    except (ValueError, IndexError):
        total_auc = float("nan")
        total_ks = float("nan")
        total_lift = {"10%": "", "5%": "", "2%": "", "1%": ""}

    date_range = _get_date_range(df, config)
    rows.append({
        "全量样本回溯": "总计",
        "观察点月": date_range,
        "样本标签": config.target_label,
        "总": total,
        "好": total_good,
        "坏": total_bad,
        "坏占比": f"{total_bad / total:.2%}" if total > 0 else "0.00%",
        "KS": round(total_ks, 2) if not np.isnan(total_ks) else "",
        "AUC": round(total_auc, 2) if not np.isnan(total_auc) else "",
        "10%lift": total_lift.get("10%", ""),
        "5%lift": total_lift.get("5%", ""),
        "2%lift": total_lift.get("2%", ""),
        "1%lift": total_lift.get("1%", ""),
    })

    return pd.DataFrame(rows)


def _build_bin_performance(df: pd.DataFrame, config: ReportConfig) -> list:
    """Build per-partition binning performance tables."""
    sc_score_col = config.sc_score_col
    target_col = config.target_col
    flag_col = config.flag_col
    partition_col = config.partition_col
    flag_labels = config.flag_labels

    results = []
    # Equal-width 10 bins for the scorecard score
    n_bins = 10

    # Per data_flag
    for flag in ["train", "test", "oot"]:
        subset = df[df[flag_col] == flag]
        if len(subset) == 0:
            continue
        labels = pd.cut(subset[sc_score_col], bins=n_bins, precision=0)
        result = calc_bin_metrics(subset[target_col], subset[sc_score_col],
                                  pd.Series(labels.cat.categories))
        results.append((flag_labels.get(flag, flag), result))

    # Per partition month
    partitions = sorted(df[partition_col].astype(str).unique())
    for part in partitions:
        subset = df[df[partition_col].astype(str) == part]
        if len(subset) < n_bins * 2:
            continue
        try:
            labels = pd.cut(subset[sc_score_col], bins=n_bins, precision=0)
            result = calc_bin_metrics(subset[target_col], subset[sc_score_col],
                                      pd.Series(labels.cat.categories))
            results.append((part, result))
        except Exception:
            continue

    return results


def _get_date_range(df: pd.DataFrame, config: ReportConfig) -> str:
    """Get date range string like '202411-202508'."""
    date_col = config.date_col
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if len(dates) == 0:
        return ""
    min_date = dates.min().strftime("%Y%m")
    max_date = dates.max().strftime("%Y%m")
    if min_date == max_date:
        return min_date
    return f"{min_date}-{max_date}"
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_model_performance.py -v
# Expected: all pass
```

- [ ] **Step 5: Commit**

```bash
git add model_report/sheets/model_performance.py tests/test_model_performance.py
git commit -m "feat: add Sheet 3 - model performance builder"
```

---

### Task 13: ReportGenerator

**Files:**
- Create: `model_report/generator.py`
- Create: `tests/test_generator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_generator.py
import pytest
import tempfile
from pathlib import Path
import pandas as pd
from model_report.config import ReportConfig
from model_report.generator import ReportGenerator


class TestReportGenerator:
    def test_generate_returns_dict(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(mock_scorecard, config)
        result = gen.generate(small_df)
        assert isinstance(result, dict)
        assert config.sheet1_name in result
        assert config.sheet2_name in result
        assert config.sheet3_name in result

    def test_generate_validates_required_columns(self, mock_scorecard):
        config = ReportConfig(target_col="mob6_30", flag_col="data_flag")
        gen = ReportGenerator(mock_scorecard, config)
        df = pd.DataFrame({"wrong_col": [1, 2, 3]})
        with pytest.raises(ValueError):
            gen.generate(df)

    def test_to_excel_creates_file(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(mock_scorecard, config)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            gen.to_excel(output_path, small_df)
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0
        finally:
            Path(output_path).unlink()

    def test_metadata_loading(self, small_df, mock_scorecard):
        config = ReportConfig(
            target_col="mob6_30",
            flag_col="data_flag",
            partition_col="part_id",
            date_col="loan_date",
            score_col="pred_score",
            sc_score_col="scorecard_score",
        )
        gen = ReportGenerator(mock_scorecard, config)
        # Should not raise with None metadata
        result = gen.generate(small_df)
        assert isinstance(result, dict)
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_generator.py -v
# Expected: ImportError
```

- [ ] **Step 3: Implement ReportGenerator**

```python
# model_report/generator.py
import pandas as pd
from model_report.config import ReportConfig
from model_report.metadata import load_variable_metadata
from model_report.writer import ExcelWriter
from model_report.sheets.model_design import build_model_design_sheet
from model_report.sheets.variable_analysis import build_variable_analysis_sheet
from model_report.sheets.model_performance import build_model_performance_sheet


class ReportGenerator:
    """Orchestrates the three sheet builders and writes the Excel report."""

    def __init__(self, scorecard, config: ReportConfig | None = None):
        self.scorecard = scorecard
        self.config = config or ReportConfig()
        self._writer = ExcelWriter()
        self._metadata = {}

    def generate(self, data: pd.DataFrame, metadata_path: str | None = None) -> dict:
        """Generate all report sheets as structured data.

        Args:
            data: Input DataFrame with scoring results.
            metadata_path: Optional path to variable metadata CSV/YAML.

        Returns:
            dict mapping sheet_name → dict[str, DataFrame].

        Raises:
            ValueError: If required columns are missing from data.
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
                 metadata_path: str | None = None) -> None:
        """Generate report and write to Excel file.

        Args:
            output_path: Path to output .xlsx file.
            data: Input DataFrame with scoring results.
            metadata_path: Optional path to variable metadata.
        """
        sheets = self.generate(data, metadata_path)
        self._writer.write(output_path, sheets)

    def _validate_data(self, data: pd.DataFrame) -> None:
        """Validate that required columns exist in the data."""
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

        # Validate target is binary {0, 1}
        target_vals = data[self.config.target_col].dropna().unique()
        if set(target_vals) - {0, 1}:
            raise ValueError(
                f"Target column '{self.config.target_col}' must contain only 0 and 1, "
                f"found: {sorted(target_vals)}"
            )

        # Validate data_flag contains train
        flag_vals = data[self.config.flag_col].unique()
        if "train" not in flag_vals:
            raise ValueError(
                f"Data must contain 'train' in '{self.config.flag_col}' column. "
                f"Found: {sorted(flag_vals)}"
            )
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_generator.py -v
# Expected: 4 passed
```

- [ ] **Step 5: Commit**

```bash
git add model_report/generator.py tests/test_generator.py
git commit -m "feat: add ReportGenerator orchestrator"
```

---

### Task 14: CLI

**Files:**
- Create: `model_report/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli.py
import pytest
from click.testing import CliRunner
from model_report.cli import main


class TestCLI:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_cli_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--model" in result.output
        assert "--data" in result.output
        assert "--output" in result.output

    def test_cli_missing_required_args(self, runner):
        result = runner.invoke(main, [])
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_cli.py -v
# Expected: ImportError
```

- [ ] **Step 3: Implement CLI**

```python
# model_report/cli.py
import click
import pandas as pd
from model_report.config import ReportConfig
from model_report.interface import PickledScorecardAdapter
from model_report.generator import ReportGenerator


@click.command()
@click.option("--model", "-m", required=True, type=click.Path(exists=True),
              help="Path to .pkl scorecard file.")
@click.option("--data", "-d", required=True, type=click.Path(exists=True),
              help="Path to scoring result CSV file.")
@click.option("--output", "-o", default="./model_report.xlsx",
              type=click.Path(), help="Output Excel path.")
@click.option("--metadata", type=click.Path(exists=True),
              help="Optional variable metadata CSV/YAML.")
@click.option("--config", type=click.Path(exists=True),
              help="Optional custom config TOML.")
def main(model, data, output, metadata, config):
    """Generate a model report Excel from scorecard and scoring data."""
    # Load config
    report_config = ReportConfig()

    # Load scorecard
    scorecard = PickledScorecardAdapter(model)

    # Load data
    if data.endswith(".csv"):
        df = pd.read_csv(data)
    elif data.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data)
    else:
        raise click.BadParameter(f"Unsupported data format: {data}")

    # Generate report
    generator = ReportGenerator(scorecard, report_config)
    generator.to_excel(output, df, metadata_path=metadata)
    click.echo(f"Report generated: {output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_cli.py -v
# Expected: 2 passed
```

- [ ] **Step 5: Update __init__.py to expose public API**

```python
# model_report/__init__.py
__version__ = "0.1.0"

from model_report.config import ReportConfig
from model_report.generator import ReportGenerator
from model_report.interface import ScorecardProtocol, PickledScorecardAdapter
```

- [ ] **Step 6: Commit**

```bash
git add model_report/cli.py tests/test_cli.py model_report/__init__.py
git commit -m "feat: add CLI and public API"
```

---

### Task 15: Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
import pytest
import tempfile
from pathlib import Path
import pandas as pd
from model_report import ReportGenerator, ReportConfig


class TestIntegration:
    """End-to-end test using real test.csv data and mock scorecard."""

    def test_full_report_generation(self, sample_df, mock_scorecard):
        # Map test.csv columns
        config = ReportConfig(
            partition_col="part_id",
            cust_col="appid",
            date_col="loan_date",
            target_col="mob6_30",
            flag_col="data_flag",
            sc_score_col="score",
        )

        gen = ReportGenerator(mock_scorecard, config)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            gen.to_excel(output_path, sample_df)

            # Verify file exists and is non-empty
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0

            # Verify sheet names
            import openpyxl
            wb = openpyxl.load_workbook(output_path)
            assert config.sheet1_name in wb.sheetnames
            assert config.sheet2_name in wb.sheetnames
            assert config.sheet3_name in wb.sheetnames

        finally:
            Path(output_path).unlink()

    def test_report_with_live_test_csv(self, sample_df, mock_scorecard):
        """Verify test.csv can be processed without errors."""
        config = ReportConfig(
            partition_col="part_id",
            cust_col="appid",
            date_col="loan_date",
            target_col="mob6_30",
            flag_col="data_flag",
            sc_score_col="score",
        )

        gen = ReportGenerator(mock_scorecard, config)
        result = gen.generate(sample_df)

        # All three sheets populated
        assert len(result) == 3
        for sheet_name, sections in result.items():
            assert len(sections) > 0
            for section_name, df in sections.items():
                if isinstance(df, pd.DataFrame):
                    assert len(df) > 0
```

- [ ] **Step 2: Run integration test**

```bash
pytest tests/test_integration.py -v
# Expected: 2 passed
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
# Expected: all tests pass
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test with test.csv"
```

---

## Completion Checklist

- [ ] All unit tests pass: `pytest tests/ -v`
- [ ] ReportGenerator generates valid Excel with 3 sheets
- [ ] CLI `--help` works
- [ ] Integration test passes with test.csv
- [ ] `model_report/metrics.py` functions verified against manual calculations
- [ ] `model_report/writer.py` data bars applied to woe/bad_rate/lift columns
