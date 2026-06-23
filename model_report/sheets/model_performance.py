import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.metrics import (
    calc_auc, calc_ks, calc_lift, calc_bin_metrics,
    calc_monthly_metrics, calc_score_psi,
)


def build_model_performance_sheet(
    data: pd.DataFrame,
    scorecard,
    config: ReportConfig,
) -> dict:
    """Build Sheet 3: Model Performance."""
    detail = scorecard.get_model_summary()
    sample_effect = _build_sample_effect(data, config)
    backtest = _build_backtest_effect(data, config)
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
    score_col = config.resolve_score_column(list(df.columns))
    sc_score_col = config.sc_score_col
    flag_labels = config.flag_labels

    # Get train set score distribution for PSI reference
    train_data = df[df[flag_col] == "train"]

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

        # PSI vs train (for train itself, PSI is "/")
        if flag == "train":
            train_psi = "/"
        elif len(train_data) > 0 and sc_score_col in df.columns:
            psi_v = calc_score_psi(train_data[sc_score_col], subset[sc_score_col])
            train_psi = f"{psi_v:.4f}"
        else:
            train_psi = ""

        # PSI vs recent month (simplified: same as train PSI for now)
        recent_psi = ""

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
            "train和各集合的PSI": train_psi,
            "近期月对比各集合PSI": recent_psi,
        })

    return pd.DataFrame(rows)


def _build_backtest_effect(df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
    """Build monthly backtest effect table."""
    target_col = config.target_col
    score_col = config.resolve_score_column(list(df.columns))
    sc_score_col = config.sc_score_col
    date_col = config.date_col
    flag_col = config.flag_col

    monthly = calc_monthly_metrics(df, target_col=target_col,
                                   score_col=score_col, date_col=date_col)

    # Train+test combined as reference for PSI
    train_test = df[df[flag_col].isin(["train", "test"])]
    # First month as reference
    first_month = monthly[monthly["观察点月"] != "all"].iloc[0]["观察点月"] \
        if len(monthly[monthly["观察点月"] != "all"]) > 0 else None
    first_month_data = df[
        df[date_col].astype(str).str.replace("-", "").str[:6] == first_month
    ] if first_month else None

    # Recent month
    recent_month = monthly[monthly["观察点月"] != "all"].iloc[-1]["观察点月"] \
        if len(monthly[monthly["观察点月"] != "all"]) > 0 else None
    recent_month_data = df[
        df[date_col].astype(str).str.replace("-", "").str[:6] == recent_month
    ] if recent_month else None

    rows = []
    for _, row in monthly.iterrows():
        month = row["观察点月"]
        if month == "all":
            continue

        month_data = df[
            df[date_col].astype(str).str.replace("-", "").str[:6] == month
        ]

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

        ks_val = row["KS"]
        auc_val = row["AUC"]

        # PSI vs first month
        first_psi = ""
        if first_month_data is not None and sc_score_col in df.columns \
                and len(first_month_data) > 0 and len(month_data) > 0:
            psi_v = calc_score_psi(first_month_data[sc_score_col], month_data[sc_score_col])
            first_psi = f"{psi_v:.4f}"

        # PSI vs recent month
        recent_psi = ""
        if recent_month_data is not None and sc_score_col in df.columns \
                and len(recent_month_data) > 0 and len(month_data) > 0:
            psi_v = calc_score_psi(recent_month_data[sc_score_col], month_data[sc_score_col])
            recent_psi = f"{psi_v:.4f}"

        rows.append({
            "全量样本回溯": partition_label,
            "观察点月": month,
            "样本标签": config.target_label,
            "总": row["总"],
            "好": row["好"],
            "坏": row["坏"],
            "坏占比": f"{row['坏样本率']:.2%}",
            "KS": round(ks_val, 2) if not isinstance(ks_val, float) or not np.isnan(ks_val) else "",
            "AUC": round(auc_val, 2) if not isinstance(auc_val, float) or not np.isnan(auc_val) else "",
            "10%lift": lift_vals.get("10%", ""),
            "5%lift": lift_vals.get("5%", ""),
            "2%lift": lift_vals.get("2%", ""),
            "1%lift": lift_vals.get("1%", ""),
            "首月与各集合的PSI": first_psi,
            "最近月对比各集合PSI": recent_psi,
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
        "首月与各集合的PSI": "",
        "最近月对比各集合PSI": "",
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
    n_bins = 10

    # Per data_flag
    for flag in ["train", "test", "oot"]:
        subset = df[df[flag_col] == flag]
        if len(subset) < n_bins * 2:
            continue
        try:
            labels = pd.cut(subset[sc_score_col], bins=n_bins, precision=0, include_lowest=True)
            result = calc_bin_metrics(subset[target_col], subset[sc_score_col],
                                      pd.Series(labels.cat.categories))
            results.append((flag_labels.get(flag, flag), result))
        except Exception:
            continue

    # Per partition month
    partitions = sorted(df[partition_col].astype(str).unique())
    for part in partitions:
        subset = df[df[partition_col].astype(str) == part]
        if len(subset) < n_bins * 2:
            continue
        try:
            labels = pd.cut(subset[sc_score_col], bins=n_bins, precision=0, include_lowest=True)
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
