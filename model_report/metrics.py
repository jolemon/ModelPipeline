import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve
from scipy import stats


def to_month(series: pd.Series) -> pd.Series:
    """Convert date series to yyyyMM string: 2025-1-6 → 202501."""
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y%m")


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


def calc_lift(df, y_col: str = "y", score_col: str = "score",
              percentiles=None, lower_is_riskier: bool = True) -> dict:
    """Calculate Lift values at given percentiles."""
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


def calc_bin_metrics(y_true, y_score, bins) -> "pd.DataFrame":
    """Calculate per-bin performance metrics."""
    import pandas as pd

    base = pd.DataFrame({"score": y_score, "label": y_true})
    base["bin"] = _assign_bins(y_score, bins)

    total_bad = int(base["label"].sum())
    total_good = int((1 - base["label"]).sum())
    total_n = len(base)
    overall_bad_rate = total_bad / total_n if total_n > 0 else 0

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


def _assign_bins(y_score, bins) -> np.ndarray:
    """Assign each score to its bin interval string, respecting interval closure.

    Handles pd.cut defaults (right=True, include_lowest=True) correctly:
    first interval includes its left boundary regardless of closed attribute.
    """
    bin_list = bins.dropna().tolist()
    result = np.empty(len(y_score), dtype=object)
    result[:] = "other"
    for i, b in enumerate(bin_list):
        closed = getattr(b, "closed", "right")
        # First bin with include_lowest=True: left boundary is inclusive
        left_inclusive = (i == 0) or (closed == "left")
        right_inclusive = (closed != "left")

        if left_inclusive:
            left_mask = y_score >= b.left
        else:
            left_mask = y_score > b.left

        if right_inclusive:
            right_mask = y_score <= b.right
        else:
            right_mask = y_score < b.right

        mask = left_mask & right_mask
        result[mask] = str(b)
    return result


def calc_score_psi(expected_scores, actual_scores, bins: int = 10) -> float:
    """Calculate PSI between two score distributions using equal-frequency binning.

    Bins are determined on the expected distribution, then the same boundaries
    are applied to the actual distribution — consistent with calc_var_psi.
    """
    import pandas as pd

    expected = np.array(expected_scores)
    actual = np.array(actual_scores)

    if len(expected) == 0 or len(actual) == 0:
        return 0.0

    try:
        _, bin_edges = pd.qcut(expected, q=bins, duplicates="drop", retbins=True)
        bin_edges = bin_edges.copy()
        bin_edges[0] = -np.inf
        bin_edges[-1] = np.inf

        expected_binned = pd.cut(expected, bins=bin_edges)
        actual_binned = pd.cut(actual, bins=bin_edges)

        expected_counts = expected_binned.value_counts().sort_index()
        actual_counts = actual_binned.value_counts().sort_index()
        expected_dist = expected_counts / expected_counts.sum()
        actual_dist = actual_counts / actual_counts.sum()

        all_bins = expected_dist.index.union(actual_dist.index)
        expected_aligned = expected_dist.reindex(all_bins, fill_value=1e-10)
        actual_aligned = actual_dist.reindex(all_bins, fill_value=1e-10)

        psi = np.sum(
            (actual_aligned - expected_aligned) *
            np.log(actual_aligned / expected_aligned)
        )
        return float(max(psi, 0.0))
    except Exception:
        return 0.0


def calc_monthly_metrics(df, target_col: str = "mob6_30",
                         score_col: str = "pred_score",
                         date_col: str = "loan_date") -> "pd.DataFrame":
    """Calculate AUC/KS/badrate by month."""
    import pandas as pd

    tmp = df.copy()
    tmp["loan_month"] = to_month(tmp[date_col])
    tmp = tmp.dropna(subset=["loan_month"])
    tmp = tmp[tmp["loan_month"] != "nan"]

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


SPECIAL_MISSING_THRESHOLD = -99999


def calc_missing_rate(series, threshold=None) -> float:
    """Calculate missing rate treating NaN and values <= threshold as missing.

    Per project convention, values <= -99999 are treated as missing.
    """
    import pandas as pd

    if threshold is None:
        threshold = SPECIAL_MISSING_THRESHOLD

    total = len(series)
    if total == 0:
        return 0.0

    numeric = pd.to_numeric(series, errors="coerce")
    nan_mask = numeric.isna()
    special_mask = numeric <= threshold
    missing_count = (nan_mask | special_mask).sum()
    return float(missing_count / total)


def calc_var_psi(train_series, oot_series) -> float:
    """Calculate PSI for a single variable between train and oot distributions."""
    import pandas as pd

    train_s = pd.Series(train_series).dropna()
    oot_s = pd.Series(oot_series).dropna()

    if len(train_s) == 0 or len(oot_s) == 0:
        return 0.0

    # Equal-frequency binning PSI - always bin on train data edges
    try:
        _, bin_edges = pd.qcut(train_s, q=10, duplicates="drop", retbins=True)
        # Extend edges to capture oot values outside train range
        bin_edges = bin_edges.copy()
        bin_edges[0] = -np.inf
        bin_edges[-1] = np.inf
        train_binned = pd.cut(train_s, bins=bin_edges)
        oot_binned = pd.cut(oot_s, bins=bin_edges)

        train_dist = train_binned.value_counts().sort_index()
        oot_dist = oot_binned.value_counts().sort_index()

        train_pct = (train_dist / train_dist.sum()).fillna(0)
        oot_pct = (oot_dist / oot_dist.sum()).fillna(0)

        all_idx = train_pct.index.union(oot_pct.index)
        train_aligned = train_pct.reindex(all_idx, fill_value=1e-10)
        oot_aligned = oot_pct.reindex(all_idx, fill_value=1e-10)

        psi_val = np.sum((oot_aligned - train_aligned) * np.log(oot_aligned / train_aligned))
        return float(max(psi_val, 0.0))
    except Exception:
        return 0.0


def calc_var_iv(df, var: str, target_col: str = "mob6_30") -> float:
    """Calculate IV for a single variable on the given dataset."""
    try:
        from toad import quality
        iv_result = quality(df[[var, target_col]], target_col, iv_only=True)
        if isinstance(iv_result, pd.Series):
            val = iv_result.get(var, 0.0)
            return float(val) if not np.isnan(float(val)) else 0.0
        return float(iv_result) if iv_result else 0.0
    except Exception:
        return 0.0


def calc_var_ks(df, var: str, target_col: str = "mob6_30") -> float:
    """Calculate KS for a single variable using scipy ks_2samp.

    Adapted from model_library/dataset_learn.py calculate_all_ks.
    Uses scipy.stats.ks_2samp between good and bad distributions.
    """
    import pandas as pd

    try:
        if var not in df.columns or target_col not in df.columns:
            return 0.0
        if not np.issubdtype(df[var].dtype, np.number):
            return 0.0

        good = df.loc[df[target_col] == 0, var].dropna()
        bad = df.loc[df[target_col] == 1, var].dropna()

        if len(good) < 2 or len(bad) < 2:
            return 0.0

        ks_stat, _ = stats.ks_2samp(bad, good)
        return float(ks_stat)
    except Exception:
        return 0.0


def calculate_all_ks(df, y_col: str = "mob6_30",
                     feature_cols=None, verbose: bool = False) -> "pd.DataFrame":
    """Batch compute KS for all feature variables.

    Adapted from model_library/dataset_learn.py calculate_all_ks.

    Args:
        df: DataFrame with features and target.
        y_col: Target column name (1 = bad).
        feature_cols: List of feature column names. If None, auto-detect.
        verbose: Print progress info.

    Returns:
        DataFrame with columns: variable, ks_scipy, ks_manual, p_value,
        ks_threshold, bad_pct_at_ks, good_pct_at_ks, sample_size, missing_rate.
    """
    import pandas as pd
    import time

    if feature_cols is None:
        feature_cols = [c for c in df.columns if c != y_col
                        and np.issubdtype(df[c].dtype, np.number)]

    good = df[df[y_col] == 0]
    bad = df[df[y_col] == 1]
    total_good = len(good)
    total_bad = len(bad)

    if total_bad < 2 or total_good < 2:
        return pd.DataFrame()

    results = []
    for col in feature_cols:
        try:
            if not np.issubdtype(df[col].dtype, np.number):
                continue

            valid_bad = bad[col].dropna()
            valid_good = good[col].dropna()

            if len(valid_bad) < 2 or len(valid_good) < 2:
                continue

            # scipy KS test
            ks_stat, p_value = stats.ks_2samp(valid_bad, valid_good)

            # Manual cumulative distribution KS (industry standard)
            df_sorted = df[[col, y_col]].dropna().sort_values(by=col, ascending=False)
            df_sorted = df_sorted.copy()
            df_sorted["cum_bad"] = df_sorted[y_col].cumsum()
            df_sorted["cum_good"] = df_sorted.index.to_series().apply(
                lambda i: i + 1
            ).values - df_sorted["cum_bad"].values
            # Actually let's do it correctly:
            df_sorted["cum_count"] = range(1, len(df_sorted) + 1)
            df_sorted["cum_bad"] = df_sorted[y_col].cumsum()
            df_sorted["cum_good"] = df_sorted["cum_count"] - df_sorted[y_col]
            df_sorted["cum_pct_bad"] = df_sorted["cum_bad"] / total_bad
            df_sorted["cum_pct_good"] = df_sorted["cum_good"] / total_good
            df_sorted["ks"] = np.abs(df_sorted["cum_pct_bad"] - df_sorted["cum_pct_good"])
            ks_manual = df_sorted["ks"].max()
            ks_point = df_sorted[df_sorted["ks"] == ks_manual].iloc[0]

            results.append({
                "variable": col,
                "ks_scipy": round(ks_stat, 4),
                "ks_manual": round(ks_manual, 4),
                "p_value": p_value,
                "ks_threshold": ks_point[col],
                "bad_pct_at_ks": round(ks_point["cum_pct_bad"], 4),
                "good_pct_at_ks": round(ks_point["cum_pct_good"], 4),
                "sample_size": len(df_sorted),
                "missing_rate": round(1 - len(df_sorted) / len(df), 4),
            })

        except Exception as e:
            if verbose:
                print(f"KS calc error for {col}: {e}")
            continue

    return pd.DataFrame(results).sort_values("ks_manual", ascending=False)


def compute_woe_table(df, var: str, target_col: str = "mob6_30",
                      bins: int = 10, good: int = 0, bad: int = 1) -> "pd.DataFrame":
    """Compute WOE/IV/KS/Lift table for a variable from data using equal-frequency binning.

    Args:
        df: DataFrame with feature and target columns.
        var: Feature column name.
        target_col: Target column name (0=good, 1=bad).
        bins: Number of equal-frequency bins for numeric variables.
        good: Value representing good in target.
        bad: Value representing bad in target.

    Returns:
        DataFrame with columns: min, max, goods, bads, total,
        good_prop, bad_prop, bad_rate, woe, iv, ks, lift.
    """
    import pandas as pd

    sub = df[[var, target_col]].copy()
    total_n = len(sub)
    total_good = int((sub[target_col] == good).sum())
    total_bad = int((sub[target_col] == bad).sum())

    if total_good == 0 or total_bad == 0:
        return pd.DataFrame()

    overall_bad_rate = total_bad / total_n

    # Determine binning method
    is_numeric = np.issubdtype(sub[var].dtype, np.number)

    if is_numeric:
        try:
            sub["_bin"], bin_edges = pd.qcut(sub[var], q=bins, duplicates="drop", retbins=True)
        except Exception:
            bin_edges = pd.cut(sub[var], bins=bins, retbins=True, duplicates="drop")[1]
            sub["_bin"] = pd.cut(sub[var], bins=bin_edges, include_lowest=True)
    else:
        # Categorical: each unique value is a bin
        sub["_bin"] = sub[var].astype(str)

    rows = []
    bin_groups = sub.groupby("_bin", observed=False)

    for bin_val, group in bin_groups:
        g = int((group[target_col] == good).sum())
        b = int((group[target_col] == bad).sum())
        t = len(group)

        if t == 0:
            continue

        good_prop = g / total_good
        bad_prop = b / total_bad
        bad_rate = b / t

        eps = 1e-10
        good_prop_safe = max(good_prop, eps)
        bad_prop_safe = max(bad_prop, eps)

        woe = np.log(bad_prop_safe / good_prop_safe)
        iv_bin = (bad_prop - good_prop) * woe
        ks_bin = abs(bad_prop - good_prop)
        lift = bad_rate / overall_bad_rate if overall_bad_rate > 0 else 0

        # Extract bin boundaries
        if is_numeric and isinstance(bin_val, pd.Interval):
            mn = bin_val.left
            mx = bin_val.right
        elif is_numeric:
            mn = mx = bin_val
        else:
            mn = mx = str(bin_val)

        rows.append({
            "min": mn,
            "max": mx,
            "goods": g,
            "bads": b,
            "total": t,
            "good_prop": good_prop,
            "bad_prop": bad_prop,
            "bad_rate": bad_rate,
            "woe": round(woe, 4),
            "iv": round(iv_bin, 4),
            "ks": round(ks_bin, 4),
            "lift": round(lift, 4),
        })

    result = pd.DataFrame(rows)

    # Sort by min for numeric, by bad_rate descending for categorical
    if is_numeric and len(result) > 0:
        result = result.sort_values("min")

    # Add ALL row
    all_row = {
        "min": "ALL", "max": "ALL",
        "goods": total_good, "bads": total_bad, "total": total_n,
        "good_prop": 1.0, "bad_prop": 1.0, "bad_rate": overall_bad_rate,
        "woe": 0.0, "iv": result["iv"].sum() if len(result) > 0 else 0.0,
        "ks": 0.0, "lift": 1.0,
    }
    result = pd.concat([result, pd.DataFrame([all_row])], ignore_index=True)

    return result
