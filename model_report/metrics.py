import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve, auc as sklearn_auc
from scipy import stats


def to_month(series: pd.Series) -> pd.Series:
    """Convert date series to yyyyMM string: 2025-1-6 → 202501."""
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y%m")


def calc_auc(y_true, y_score, sample_weight=None) -> float:
    """Calculate AUC — trapezoidal method matching model_learn model_metrics_v4.

    Uses good=1 as positive class (consistent with model_library/model_learn.py).
    """
    unique_labels = np.unique(y_true)
    if len(unique_labels) < 2:
        raise ValueError("y_true must contain both positive and negative samples for AUC")
    good_flag = 1 - np.array(y_true)  # good=1, bad=0
    fpr, tpr, _ = roc_curve(good_flag, y_score, pos_label=1, sample_weight=sample_weight)
    return float(sklearn_auc(fpr, tpr))


def calc_ks(y_true, y_score, sample_weight=None) -> float:
    """Calculate KS — matching model_learn model_metrics_v4.

    Uses good=1 as positive class (consistent with model_library/model_learn.py).
    """
    good_flag = 1 - np.array(y_true)  # good=1, bad=0
    fpr, tpr, _ = roc_curve(good_flag, y_score, pos_label=1, sample_weight=sample_weight)
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
                         date_col: str = "loan_date",
                         loan_amount_col: str = "") -> "pd.DataFrame":
    """Calculate AUC/KS/badrate by month.

    If loan_amount_col is provided and exists in df, also computes
    amount-weighted AUC/KS (matching model_learn calc_auc_ks_by_month).
    """
    import pandas as pd

    tmp = df.copy()
    tmp["loan_month"] = to_month(tmp[date_col])
    tmp = tmp.dropna(subset=["loan_month"])
    tmp = tmp[tmp["loan_month"] != "nan"]

    has_amount = bool(loan_amount_col) and loan_amount_col in tmp.columns

    rows = []
    months = sorted(tmp["loan_month"].unique())
    n_months = len(months)
    for mi, m in enumerate(months + ["all"]):
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

        # Standard AUC/KS
        std_auc, std_ks = float("nan"), float("nan")
        try:
            std_auc = calc_auc(m_data[target_col], m_data[score_col])
            std_ks = calc_ks(m_data[target_col], m_data[score_col])
        except ValueError:
            pass

        # Amount-weighted AUC/KS
        amt_auc, amt_ks = "", ""
        if has_amount:
            weights = m_data[loan_amount_col].astype(float)
            if weights.sum() > 0:
                try:
                    amt_auc = round(calc_auc(m_data[target_col], m_data[score_col],
                                             sample_weight=weights), 4)
                    amt_ks = round(calc_ks(m_data[target_col], m_data[score_col],
                                           sample_weight=weights), 4)
                except ValueError:
                    pass

        row = {
            "观察点月": m,
            "总": total,
            "好": good,
            "坏": bad,
            "坏样本率": round(badrate, 4),
            "KS": round(std_ks, 4) if not np.isnan(std_ks) else std_ks,
            "AUC": round(std_auc, 4) if not np.isnan(std_auc) else std_auc,
        }
        if has_amount:
            row["金额KS"] = amt_ks if amt_ks != "" else ""
            row["金额AUC"] = amt_auc if amt_auc != "" else ""
        rows.append(row)
        if m != "all":
            print(f"\r    回溯效果 ({mi+1}/{n_months}): {m}", end="", flush=True)

    print(f"\r    回溯效果: {n_months}/{n_months} ✓")
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
        # toad.quality returns DataFrame with 'iv' column, vars as index
        if isinstance(iv_result, pd.DataFrame) and "iv" in iv_result.columns:
            return float(iv_result["iv"].iloc[0]) if len(iv_result) > 0 else 0.0
        if isinstance(iv_result, pd.Series):
            return float(iv_result.iloc[0]) if len(iv_result) > 0 else 0.0
        return 0.0
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
                      good: int = 0, bad: int = 1,
                      min_samples_pct: float = 0.03,
                      max_samples_pct: float = 0.5) -> "pd.DataFrame":
    """Compute WOE/IV/KS/Lift table with monotonic binning and missing value handling.

    Adapted from model_library/dataset_learn.py monotonic_binning.

    Algorithm:
        1. Separate special-missing values (NaN, <= -99999) into a MISSING_VALUE bin
        2. Fine equal-frequency binning (20 bins via percentiles)
        3. Merge micro-bins to satisfy [min_samples_pct, max_samples_pct] proportion
        4. Enforce WOE monotonicity (increase) by merging adjacent bins
        5. Prepend MISSING_VALUE bin (if any missing samples)
        6. Append ALL summary row

    Args:
        df: DataFrame with feature and target columns.
        var: Feature column name.
        target_col: Target column name (0=good, 1=bad).
        good: Value representing good in target.
        bad: Value representing bad in target.
        min_samples_pct: Minimum samples per bin as fraction of total (default 3%).
        max_samples_pct: Maximum samples per bin as fraction of total (default 50%).

    Returns:
        DataFrame with columns: min, max, goods, bads, total,
        good_prop, bad_prop, bad_rate, woe, iv, ks, lift.
        Returns empty DataFrame if good or bad count is 0.
    """
    import pandas as pd

    sub = df[[var, target_col]].copy()
    total_n = len(sub)
    total_good = int((sub[target_col] == good).sum())
    total_bad = int((sub[target_col] == bad).sum())

    if total_good == 0 or total_bad == 0:
        return pd.DataFrame()

    overall_bad_rate = total_bad / total_n
    is_numeric = np.issubdtype(sub[var].dtype, np.number)

    # ── Categorical: each unique value is a bin (no merging needed) ──
    if not is_numeric:
        return _categorical_woe_table(sub, var, target_col, total_n,
                                       total_good, total_bad, overall_bad_rate,
                                       good, bad)

    # ── Numeric: monotonic binning ──
    return _numeric_monotonic_woe_table(sub, var, target_col, total_n,
                                         total_good, total_bad, overall_bad_rate,
                                         good, bad, min_samples_pct, max_samples_pct)


def _categorical_woe_table(sub, var, target_col, total_n, total_good, total_bad,
                            overall_bad_rate, good, bad):
    """WOE table for categorical variable: one bin per unique value."""
    import pandas as pd

    sub["_bin"] = sub[var].astype(str)
    rows = []
    for bin_val, group in sub.groupby("_bin", observed=False):
        g = int((group[target_col] == good).sum())
        b = int((group[target_col] == bad).sum())
        t = len(group)
        if t == 0:
            continue
        rows.append(_make_bin_row(bin_val, bin_val, g, b, t,
                                   total_good, total_bad, overall_bad_rate))

    result = pd.DataFrame(rows)
    result = result.sort_values("bad_rate", ascending=False)
    return _append_all_row(result, total_good, total_bad, total_n, overall_bad_rate)


def _numeric_monotonic_woe_table(sub, var, target_col, total_n, total_good,
                                  total_bad, overall_bad_rate, good, bad,
                                  min_samples_pct, max_samples_pct):
    """Monotonic binning for numeric variable."""
    import pandas as pd

    # ── 1. Separate missing / special values ──
    missing_values = [v for v in [float("-inf"), float("inf")] if False]  # placeholder
    special_mask = sub[var].isna() | (pd.to_numeric(sub[var], errors="coerce") <= -99999)
    # Cast to float after handling non-numeric
    numeric_var = pd.to_numeric(sub[var], errors="coerce")
    special_mask = numeric_var.isna() | (numeric_var <= -99999)

    valid_mask = ~special_mask
    valid_data = numeric_var[valid_mask]
    valid_target = sub.loc[valid_mask, target_col]

    if len(valid_data) == 0:
        return pd.DataFrame()

    # ── 2. Initial fine binning via percentiles ──
    n_init = 20
    if len(valid_data) < n_init * 10:
        n_init = max(5, len(valid_data) // 10)
    percentiles = np.linspace(0, 100, n_init + 1)[1:-1]
    init_bins = np.percentile(valid_data, percentiles)
    init_bins = np.unique(init_bins)
    bin_edges = np.concatenate(([-np.inf], init_bins, [np.inf]))
    bin_idx = np.digitize(valid_data, bin_edges) - 1

    micro_stats = []
    for i in range(len(bin_edges) - 1):
        mask = (bin_idx == i)
        if mask.sum() == 0:
            continue
        g = int((valid_target[mask] == good).sum())
        b = int((valid_target[mask] == bad).sum())
        t = int(mask.sum())
        micro_stats.append({
            "min": bin_edges[i], "max": bin_edges[i + 1],
            "goods": g, "bads": b, "total": t,
        })

    if not micro_stats:
        return pd.DataFrame()

    micro_df = pd.DataFrame(micro_stats)
    micro_df["total_pct"] = micro_df["total"] / total_n

    # ── 3. Merge micro-bins to satisfy proportion constraints ──
    final_bins = []
    current = {"min": None, "max": None, "goods": 0, "bads": 0, "total": 0}
    for _, row in micro_df.iterrows():
        if current["min"] is None:
            current["min"] = row["min"]
        current["max"] = row["max"]
        current["goods"] += row["goods"]
        current["bads"] += row["bads"]
        current["total"] += row["total"]
        cur_pct = current["total"] / total_n

        if cur_pct > max_samples_pct:
            if current["total"] == row["total"]:
                final_bins.append(current.copy())
                current = {"min": None, "max": None, "goods": 0, "bads": 0, "total": 0}
            else:
                current["goods"] -= row["goods"]
                current["bads"] -= row["bads"]
                current["total"] -= row["total"]
                final_bins.append(current.copy())
                current = {"min": row["min"], "max": row["max"],
                           "goods": row["goods"], "bads": row["bads"],
                           "total": row["total"]}
        elif cur_pct >= min_samples_pct:
            final_bins.append(current.copy())
            current = {"min": None, "max": None, "goods": 0, "bads": 0, "total": 0}

    if current["total"] > 0:
        if current["total"] / total_n < min_samples_pct and len(final_bins) > 0:
            final_bins[-1]["max"] = current["max"]
            final_bins[-1]["goods"] += current["goods"]
            final_bins[-1]["bads"] += current["bads"]
            final_bins[-1]["total"] += current["total"]
        else:
            final_bins.append(current)

    if len(final_bins) < 2:
        return _fallback_qcut_woe(sub, var, target_col, total_n, total_good,
                                   total_bad, overall_bad_rate, good, bad)

    # ── 4. Compute metrics ──
    def compute_metrics(bin_list):
        rows = []
        for b in bin_list:
            rows.append(_make_bin_row(b["min"], b["max"], b["goods"], b["bads"],
                                       b["total"], total_good, total_bad,
                                       overall_bad_rate))
        return pd.DataFrame(rows)

    df_valid = compute_metrics(final_bins)

    # ── 5. Enforce WOE monotonicity (increase) ──
    for _ in range(10):
        woe_vals = df_valid["woe"].values
        if _is_monotonic_increase(woe_vals):
            break
        # Find first pair that breaks monotonicity
        merge_idx = -1
        for i in range(len(woe_vals) - 1):
            if woe_vals[i] > woe_vals[i + 1]:
                merge_idx = i
                break
        if merge_idx == -1:
            break
        # Merge adjacent bins
        merged = {
            "min": df_valid.iloc[merge_idx]["min"],
            "max": df_valid.iloc[merge_idx + 1]["max"],
            "goods": int(df_valid.iloc[merge_idx]["goods"]) + int(df_valid.iloc[merge_idx + 1]["goods"]),
            "bads": int(df_valid.iloc[merge_idx]["bads"]) + int(df_valid.iloc[merge_idx + 1]["bads"]),
            "total": int(df_valid.iloc[merge_idx]["total"]) + int(df_valid.iloc[merge_idx + 1]["total"]),
        }
        df_valid = pd.concat([
            df_valid.iloc[:merge_idx],
            compute_metrics([merged]),
            df_valid.iloc[merge_idx + 2:],
        ], ignore_index=True)
        if len(df_valid) < 2:
            break

    # ── 5b. Merge to target bin count, re-enforce monotonicity each step ──
    target_max = 6
    for _ in range(20):  # safety limit
        if len(df_valid) <= target_max:
            break
        # Merge the adjacent pair with smallest absolute WOE gap
        woe_vals = df_valid["woe"].values
        best_idx = 0
        best_gap = abs(woe_vals[0] - woe_vals[1])
        for i in range(1, len(woe_vals) - 1):
            gap = abs(woe_vals[i] - woe_vals[i + 1])
            if gap < best_gap:
                best_gap = gap
                best_idx = i
        merged = {
            "min": df_valid.iloc[best_idx]["min"],
            "max": df_valid.iloc[best_idx + 1]["max"],
            "goods": int(df_valid.iloc[best_idx]["goods"]) + int(df_valid.iloc[best_idx + 1]["goods"]),
            "bads": int(df_valid.iloc[best_idx]["bads"]) + int(df_valid.iloc[best_idx + 1]["bads"]),
            "total": int(df_valid.iloc[best_idx]["total"]) + int(df_valid.iloc[best_idx + 1]["total"]),
        }
        df_valid = pd.concat([
            df_valid.iloc[:best_idx],
            compute_metrics([merged]),
            df_valid.iloc[best_idx + 2:],
        ], ignore_index=True)
        # Re-enforce monotonicity after merge
        woe_vals2 = df_valid["woe"].values
        if not _is_monotonic_increase(woe_vals2):
            for j in range(len(woe_vals2) - 1):
                if woe_vals2[j] > woe_vals2[j + 1]:
                    merged2 = {
                        "min": df_valid.iloc[j]["min"],
                        "max": df_valid.iloc[j + 1]["max"],
                        "goods": int(df_valid.iloc[j]["goods"]) + int(df_valid.iloc[j + 1]["goods"]),
                        "bads": int(df_valid.iloc[j]["bads"]) + int(df_valid.iloc[j + 1]["bads"]),
                        "total": int(df_valid.iloc[j]["total"]) + int(df_valid.iloc[j + 1]["total"]),
                    }
                    df_valid = pd.concat([
                        df_valid.iloc[:j],
                        compute_metrics([merged2]),
                        df_valid.iloc[j + 2:],
                    ], ignore_index=True)
                    break

    # ── 5c. Final monotonicity check (iterate until fixed) ──
    for _ in range(10):
        woe_final = df_valid["woe"].values
        if _is_monotonic_increase(woe_final):
            break
        for k in range(len(woe_final) - 1):
            if woe_final[k] > woe_final[k + 1]:
                merged_final = {
                    "min": df_valid.iloc[k]["min"],
                    "max": df_valid.iloc[k + 1]["max"],
                    "goods": int(df_valid.iloc[k]["goods"]) + int(df_valid.iloc[k + 1]["goods"]),
                    "bads": int(df_valid.iloc[k]["bads"]) + int(df_valid.iloc[k + 1]["bads"]),
                    "total": int(df_valid.iloc[k]["total"]) + int(df_valid.iloc[k + 1]["total"]),
                }
                df_valid = pd.concat([
                    df_valid.iloc[:k],
                    compute_metrics([merged_final]),
                    df_valid.iloc[k + 2:],
                ], ignore_index=True)
                break

    # ── 6. Missing bin ──
    result = df_valid
    if special_mask.any():
        missing_goods = int((sub.loc[special_mask, target_col] == good).sum())
        missing_bads = int((sub.loc[special_mask, target_col] == bad).sum())
        missing_total = int(special_mask.sum())
        if missing_total > 0:
            missing_row = _make_bin_row("MISSING_VALUE", "MISSING_VALUE",
                                         missing_goods, missing_bads, missing_total,
                                         total_good, total_bad, overall_bad_rate)
            result = pd.concat([pd.DataFrame([missing_row]), df_valid], ignore_index=True)

    # ── 7. ALL row ──
    return _append_all_row(result, total_good, total_bad, total_n, overall_bad_rate)


def _make_bin_row(mn, mx, g, b, t, total_good, total_bad, overall_bad_rate) -> dict:
    """Create a single bin row with all metrics."""
    good_prop = g / total_good if total_good > 0 else 0
    bad_prop = b / total_bad if total_bad > 0 else 0
    bad_rate = b / t if t > 0 else 0
    eps = 1e-10
    woe = np.log(max(bad_prop, eps) / max(good_prop, eps))
    iv = (bad_prop - good_prop) * woe
    ks = abs(bad_prop - good_prop)
    lift = bad_rate / overall_bad_rate if overall_bad_rate > 0 else 0
    return {
        "min": mn, "max": mx,
        "goods": g, "bads": b, "total": t,
        "good_prop": good_prop, "bad_prop": bad_prop,
        "bad_rate": round(bad_rate, 4), "woe": round(woe, 4),
        "iv": round(iv, 4), "ks": round(ks, 4), "lift": round(lift, 4),
    }


def _is_monotonic_increase(arr) -> bool:
    """Check if values are monotonically non-decreasing."""
    return all(arr[i] <= arr[i + 1] for i in range(len(arr) - 1))


def _append_all_row(result, total_good, total_bad, total_n, overall_bad_rate):
    """Append ALL summary row."""
    import pandas as pd
    all_row = {
        "min": "ALL", "max": "ALL",
        "goods": total_good, "bads": total_bad, "total": total_n,
        "good_prop": 1.0, "bad_prop": 1.0, "bad_rate": overall_bad_rate,
        "woe": 0.0, "iv": result["iv"].sum() if len(result) > 0 else 0.0,
        "ks": 0.0, "lift": 1.0,
    }
    return pd.concat([result, pd.DataFrame([all_row])], ignore_index=True)


def _fallback_qcut_woe(sub, var, target_col, total_n, total_good, total_bad,
                        overall_bad_rate, good, bad):
    """Fallback: simple equal-frequency binning when monotonic merge fails."""
    import pandas as pd
    try:
        sub["_bin"] = pd.qcut(pd.to_numeric(sub[var], errors="coerce"),
                               q=5, duplicates="drop")
    except Exception:
        sub["_bin"] = pd.cut(pd.to_numeric(sub[var], errors="coerce"),
                              bins=5, include_lowest=True, duplicates="drop")
    rows = []
    for bin_val, group in sub.groupby("_bin", observed=False):
        g = int((group[target_col] == good).sum())
        b = int((group[target_col] == bad).sum())
        t = len(group)
        if t == 0:
            continue
        mn = bin_val.left if hasattr(bin_val, "left") else str(bin_val)
        mx = bin_val.right if hasattr(bin_val, "right") else str(bin_val)
        rows.append(_make_bin_row(mn, mx, g, b, t, total_good, total_bad, overall_bad_rate))
    result = pd.DataFrame(rows).sort_values("min")
    return _append_all_row(result, total_good, total_bad, total_n, overall_bad_rate)
