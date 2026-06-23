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
    """Assign each score to its bin interval string."""
    bin_list = bins.dropna().tolist()
    result = np.empty(len(y_score), dtype=object)
    result[:] = "other"
    for b in bin_list:
        mask = (y_score >= b.left) & (y_score < b.right)
        result[mask] = str(b)
    return result


def calc_score_psi(expected_scores, actual_scores, bins: int = 10) -> float:
    """Calculate PSI between two score distributions using equal-width binning."""
    import pandas as pd

    expected = np.array(expected_scores)
    actual = np.array(actual_scores)

    min_val = min(expected.min(), actual.min())
    max_val = max(expected.max(), actual.max())
    bin_edges = np.linspace(min_val, max_val, bins + 1)
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
    return float(psi)


def calc_monthly_metrics(df, target_col: str = "mob6_30",
                         score_col: str = "pred_score",
                         date_col: str = "loan_date") -> "pd.DataFrame":
    """Calculate AUC/KS/badrate by month."""
    import pandas as pd

    tmp = df.copy()
    tmp["loan_month"] = tmp[date_col].astype(str).str.replace("-", "").str[:6]
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
