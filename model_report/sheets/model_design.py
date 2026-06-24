import pandas as pd
from model_report.config import ReportConfig
from model_report.metrics import to_month


def build_model_design_sheet(data: pd.DataFrame, config: ReportConfig) -> dict:
    """Build Sheet 1: Model Design.

    Produces:
        partition_distribution — breakdown by data_flag × partition
        modeling_score — train/test/oot summary
    """
    # 1.1 Partition distribution
    part_dist = _build_partition_distribution(data, config)

    # 1.2 Modeling score summary
    score_summary = _build_modeling_score(data, config)

    return {
        "partition_distribution": part_dist,
        "modeling_score": score_summary,
    }


def _build_partition_distribution(df: pd.DataFrame, config: ReportConfig) -> pd.DataFrame:
    """Build partition distribution table, grouped by loan_month × data_flag."""
    flag_col = config.flag_col
    target_col = config.target_col
    date_col = config.date_col
    flag_labels = config.flag_labels

    # Derive month from date column (2025-01-15 → 202501)
    df = df.copy()
    df["_loan_month"] = to_month(df[date_col])

    rows = []
    months = sorted(df["_loan_month"].unique())

    for month in months:
        for flag in ["train", "test", "oot", "oos"]:
            subset = df[(df["_loan_month"] == month) & (df[flag_col] == flag)]
            if len(subset) == 0:
                continue
            bad = int(subset[target_col].sum())
            total = len(subset)
            good = total - bad
            bad_rate = bad / total if total > 0 else 0
            rows.append({
                "样本数据集划分标签": flag_labels.get(flag, flag),
                "样本分区": month,
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
