import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.metrics import (
    calc_var_psi, calc_var_iv, calc_var_ks, calc_missing_rate, compute_woe_table,
    _is_monotonic_increase,
)


def build_variable_analysis_sheet(
    data: pd.DataFrame,
    scorecard,
    config: ReportConfig,
    metadata: dict,
) -> dict:
    """Build Sheet 2: Variable Analysis.

    All metrics are computed directly from the scoring data.
    If scorecard is provided, analysis is restricted to the model's
    variable list and sorted by Wald-Chi2 descending.
    """
    feature_cols = config.get_feature_columns(list(data.columns))

    # If scorecard available, restrict to model variables + sort by Wald-Chi2
    wald_order = None
    if scorecard is not None:
        model_vars = scorecard.get_var_names()
        if model_vars:
            feature_cols = [v for v in feature_cols if v in model_vars]
        # Build Wald-Chi2 ranking from model summary
        summary = scorecard.get_model_summary()
        if not summary.empty and "Parameter" in summary.columns and "Wald-Chi2" in summary.columns:
            wald_rank = summary[summary["Parameter"] != "intercept"] \
                .sort_values("Wald-Chi2", ascending=False)
            wald_order = wald_rank["Parameter"].tolist()

    # 2.1 Variable overview (sorted by Wald-Chi2 if available, else IV)
    overview = _build_variable_overview(data, feature_cols, config, metadata)

    # Apply Wald-Chi2 sort if available
    if wald_order:
        overview = _sort_by_order(overview, wald_order)

    # 2.2 Top N WOE tables
    top_n = config.top_n_vars
    top_vars = _get_top_vars(overview, top_n)
    top10 = []
    train_data = data[data[config.flag_col] == "train"]
    for var in top_vars:
        if len(train_data) > 0:
            woe_df = compute_woe_table(train_data, var=var, target_col=config.target_col)
            if woe_df is not None and not woe_df.empty:
                top10.append((var, _format_woe_table(woe_df)))

    # 2.3 Variable filter summary
    filter_summary = _build_filter_summary(data, feature_cols, overview, scorecard, config)

    return {
        "变量总览": overview,
        "Top10 单变量 WOE 分箱分析": top10,
        "变量筛选": filter_summary,
    }


def _sort_by_order(df: pd.DataFrame, order: list) -> pd.DataFrame:
    """Sort DataFrame so that 变量名 column matches the given order list."""
    order_map = {v: i for i, v in enumerate(order)}
    df["_sort_key"] = df["变量名"].map(lambda x: order_map.get(x, 9999))
    df = df.sort_values("_sort_key").drop(columns=["_sort_key"])
    df["序号"] = range(1, len(df) + 1)
    return df


def _get_top_vars(overview: pd.DataFrame, top_n: int) -> list:
    """Get top N variable names sorted by iv_train descending."""
    if len(overview) == 0:
        return []
    return overview.head(top_n)["变量名"].tolist()


def _build_filter_summary(data, feature_cols, overview, scorecard, config):
    """Build variable filter summary table with cumulative counts."""
    flag_col = config.flag_col
    target_col = config.target_col
    total_vars = len(feature_cols)
    if total_vars == 0:
        return None

    train_data = data[data[flag_col] == "train"]
    oot_data = data[data[flag_col] == "oot"]

    # Compute per-variable filter results
    overview["_missing_max"] = overview.apply(
        lambda r: max(
            float(str(r["缺失率_train"]).rstrip("%")) / 100 if r["缺失率_train"] else 0,
            float(str(r["缺失率_oot"]).rstrip("%")) / 100 if r["缺失率_oot"] else 0,
        ), axis=1
    )
    overview["_iv_num"] = pd.to_numeric(overview["iv_train"], errors="coerce").fillna(0)
    overview["_psi_num"] = pd.to_numeric(overview["psi"], errors="coerce").fillna(999)
    overview["_ks_train_num"] = pd.to_numeric(overview["ks_train"], errors="coerce").fillna(0)
    overview["_ks_oot_num"] = pd.to_numeric(overview["ks_oot"], errors="coerce").fillna(0)

    # Check WOE monotonicity for business interpretability
    def check_monotonic(var_name):
        if len(train_data) == 0:
            return False
        woe_df = compute_woe_table(train_data, var=var_name, target_col=target_col)
        if woe_df.empty:
            return False
        woe_vals = woe_df.loc[~woe_df["min"].isin(["ALL", "MISSING_VALUE"]), "woe"].values
        if len(woe_vals) < 2:
            return False
        return _is_monotonic_increase(woe_vals)

    overview["_monotonic"] = overview["变量名"].apply(check_monotonic)

    # Cumulative filter application
    rows = []
    passing = set(overview["变量名"].tolist())

    def apply_filter(name, condition, threshold_label):
        nonlocal passing
        passing = {v for v in passing if condition(v)}
        rows.append({
            "筛选阶段": "粗筛",
            "指标": name,
            "阈值": threshold_label,
            "剩余变量数": len(passing),
        })

    def var_ok(v, col):
        return overview.loc[overview["变量名"] == v, col].iloc[0]

    apply_filter("PSI", lambda v: var_ok(v, "_psi_num") < 0.06, "<0.06")
    apply_filter("缺失率", lambda v: var_ok(v, "_missing_max") < 0.10, "<0.10")
    apply_filter("IV", lambda v: var_ok(v, "_iv_num") > 0.15, ">0.15")
    apply_filter("与目标相关性", lambda v: (
        var_ok(v, "_ks_train_num") > 0 and var_ok(v, "_ks_oot_num") > 0
    ), "训练/验证前后一致")
    apply_filter("业务解释", lambda v: var_ok(v, "_monotonic"), "WOE单调性符合逻辑")

    # Stepwise regression filters (scorecard only)
    if scorecard is not None:
        summary = scorecard.get_model_summary()
        if not summary.empty and "VIF" in summary.columns and "P-value-num" in summary.columns:
            summary_vars = summary[summary["Parameter"] != "intercept"]
            vif_map = dict(zip(summary_vars["Parameter"], summary_vars["VIF"]))
            pval_map = dict(zip(summary_vars["Parameter"], summary_vars["P-value-num"]))

            def get_vif(v):
                return vif_map.get(v, 999)

            def get_pval(v):
                return pval_map.get(v, 1.0)

            apply_filter("变量相关性(VIF)", lambda v: get_vif(v) < 3, "<3")
            apply_filter("VIF", lambda v: get_vif(v) < 4, "<4")
            apply_filter("P-value", lambda v: get_pval(v) < 0.01, "<0.01")

    return pd.DataFrame(rows) if rows else None
    """Sort DataFrame so that 变量名 column matches the given order list."""
    order_map = {v: i for i, v in enumerate(order)}
    df["_sort_key"] = df["变量名"].map(lambda x: order_map.get(x, 9999))
    df = df.sort_values("_sort_key").drop(columns=["_sort_key"])
    df["序号"] = range(1, len(df) + 1)
    return df


def _get_top_vars(overview: pd.DataFrame, top_n: int) -> list:
    """Get top N variable names sorted by iv_train descending."""
    if len(overview) == 0:
        return []
    return overview.head(top_n)["变量名"].tolist()


def _build_variable_overview(
    data: pd.DataFrame,
    feature_cols: list,
    config: ReportConfig,
    metadata: dict,
) -> pd.DataFrame:
    """Build the variable IV/KS/PSI overview table — all computed from data."""
    rows = []
    flag_col = config.flag_col

    train_data = data[data[flag_col] == "train"]
    oot_data = data[data[flag_col] == "oot"]

    for idx, var in enumerate(feature_cols, 1):
        var_meta = metadata.get(var, {})
        dtype = str(data[var].dtype)

        # Missing rate
        missing_train = calc_missing_rate(train_data[var]) if len(train_data) > 0 else 0
        missing_oot = calc_missing_rate(oot_data[var]) if len(oot_data) > 0 else 0

        # Train IV — computed from data
        iv_train = calc_var_iv(train_data, var, config.target_col) if len(train_data) > 0 else np.nan
        iv_train_val = f"{iv_train:.2f}" if not np.isnan(iv_train) else ""

        # OOT IV
        oot_iv = calc_var_iv(oot_data, var, config.target_col) if len(oot_data) > 0 else np.nan
        oot_iv_val = f"{oot_iv:.2f}" if not np.isnan(oot_iv) else ""

        # Train KS — computed from data
        ks_train = calc_var_ks(train_data, var, config.target_col) if len(train_data) > 0 else np.nan
        ks_train_val = f"{ks_train:.2f}" if not np.isnan(ks_train) else ""

        # OOT KS
        oot_ks = calc_var_ks(oot_data, var, config.target_col) if len(oot_data) > 0 else np.nan
        oot_ks_val = f"{oot_ks:.2f}" if not np.isnan(oot_ks) else ""

        # PSI
        psi_val = calc_var_psi(train_data[var], oot_data[var]) if len(train_data) > 0 and len(oot_data) > 0 else 0
        psi_str = f"{psi_val:.4f}"

        rows.append({
            "序号": idx,
            "变量名": var,
            "变量解释含义": var_meta.get("变量解释含义", ""),
            "来源": var_meta.get("来源", ""),
            "表描述": var_meta.get("表描述", ""),
            "数据类型": dtype,
            "缺失率_train": f"{missing_train:.2%}",
            "缺失率_oot": f"{missing_oot:.2%}",
            "iv_train": iv_train_val,
            "iv_oot": oot_iv_val,
            "ks_train": ks_train_val,
            "ks_oot": oot_ks_val,
            "psi": psi_str,
        })

    df = pd.DataFrame(rows)

    # Sort by IV descending
    if len(df) > 0:
        df["_iv_sort"] = pd.to_numeric(df["iv_train"], errors="coerce").fillna(0)
        df = df.sort_values("_iv_sort", ascending=False).drop(columns=["_iv_sort"])
        df["序号"] = range(1, len(df) + 1)

    return df


def _format_woe_table(woe_df: pd.DataFrame) -> pd.DataFrame:
    """Format WOE table columns for Excel output matching readme.md spec layout."""
    # compute_woe_table already outputs the right column names.
    # We just need to format inf values and percentages.

    out = woe_df.copy()

    # Format min/max: inf/NaN as strings, numeric values to 2 decimal places
    for col in ["min", "max"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: "-inf" if (isinstance(x, float) and x == float("-inf")) or pd.isna(x)
                else ("inf" if isinstance(x, float) and x == float("inf")
                      else ("ALL" if x == "ALL"
                            else f"{float(x):.2f}" if isinstance(x, (int, float)) else x))
            )

    # All metric columns kept numeric — Excel number format handles display
    # (good_prop/bad_prop use 0.00%, iv/ks/lift use 0.00, bad_rate 0.0000)

    final_cols = ["min", "max", "goods", "bads", "total", "good_prop", "bad_prop",
                  "bad_rate", "woe", "iv", "ks", "lift"]
    result_cols = [c for c in final_cols if c in out.columns]
    return out[result_cols] if result_cols else out
