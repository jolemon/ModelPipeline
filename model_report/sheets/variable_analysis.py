import pandas as pd
import numpy as np
from model_report.config import ReportConfig
from model_report.metrics import (
    calc_var_psi, calc_var_iv, calc_var_ks, calc_missing_rate,
)


def build_variable_analysis_sheet(
    data: pd.DataFrame,
    scorecard,
    config: ReportConfig,
    metadata: dict,
) -> dict:
    """Build Sheet 2: Variable Analysis."""
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

        # Missing rate (including special missing values)
        missing_train = calc_missing_rate(train_data[var]) if len(train_data) > 0 else 0
        missing_oot = calc_missing_rate(oot_data[var]) if len(oot_data) > 0 else 0

        # IV
        iv_train = float(iv_table.get(var, np.nan)) if isinstance(iv_table, pd.Series) else np.nan
        iv_train_val = round(iv_train, 2) if not np.isnan(iv_train) else ""

        # OOT IV
        oot_iv = calc_var_iv(oot_data, var, config.target_col) if len(oot_data) > 0 else np.nan
        oot_iv_val = f"{oot_iv:.2f}" if not np.isnan(oot_iv) else ""

        # KS
        ks_train = float(ks_table.get(var, np.nan)) if isinstance(ks_table, pd.Series) else np.nan
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

    out = pd.DataFrame()
    for src, dst in col_map.items():
        if src in woe_df.columns:
            out[dst] = woe_df[src]

    # Compute KS before formatting (use raw float values from woe_df)
    if "ks" not in out.columns and "%Good" in woe_df.columns and "%Bad" in woe_df.columns:
        out["ks"] = abs(woe_df["%Good"].astype(float) - woe_df["%Bad"].astype(float))

    # Convert inf values in min/max to string representations
    for col in ["min", "max"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: "-inf" if (isinstance(x, float) and x == float("-inf")) or pd.isna(x)
                else ("inf" if isinstance(x, float) and x == float("inf") else x)
            )

    # Format proportion columns as percentages
    for col in ["good_prop", "bad_prop"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: f"{float(x):.2%}" if pd.notna(x) and x != "" else x
            )

    # Format bad_rate as percentage
    if "bad_rate" in out.columns:
        out["bad_rate"] = out["bad_rate"].apply(
            lambda x: f"{float(x):.2%}" if pd.notna(x) and x != "" else x
        )

    # Consistent column order
    final_cols = ["min", "max", "goods", "bads", "total", "good_prop", "bad_prop",
                  "bad_rate", "woe", "iv", "ks", "lift"]
    result_cols = [c for c in final_cols if c in out.columns]
    return out[result_cols] if result_cols else out
