"""Generate a sample model report for style review."""
import pandas as pd
import numpy as np
from unittest.mock import MagicMock
from model_report import ReportGenerator, ReportConfig

np.random.seed(42)

# ── Build realistic sample data ──
n = 500
partitions = {
    "202411": 60, "202412": 60, "202501": 60, "202502": 60,
    "202503": 60, "202504": 60, "202505": 60, "202506": 40,
    "202507": 40,
}
data_rows = []
for part, cnt in partitions.items():
    for i in range(cnt):
        target = np.random.binomial(1, 0.08)
        pred = np.random.beta(1 + target * 3, 3 - target * 2)
        sc = int(400 + pred * 500 + np.random.normal(0, 20))
        sc = max(300, min(950, sc))

        if part < "202505":
            flag = np.random.choice(["train", "test"], p=[0.8, 0.2])
        elif part < "202507":
            flag = "oot"
        else:
            flag = "oos"

        data_rows.append({
            "part_id": part,
            "cert_no": f"id_{part}_{i:04d}",
            "loan_date": f"{part[:4]}-{part[4:]}-{np.random.randint(1,28):02d}",
            "mob6_30": target,
            "data_flag": flag,
            "pred_score": round(pred, 4),
            "scorecard_score": sc,
            "txriskscorev7": np.random.randint(1, 60),
            "rat1_sum_bu_1_14_pboc_aj65_cur": round(np.random.uniform(0, 2), 6),
            "cu_ln_acct_lurate_gt50_arto": round(np.random.beta(2, 5), 4),
            "r24m_cfcbnkndpst_noacct_ln_tac": np.random.choice([0, 1, 2], p=[0.3, 0.4, 0.3]),
            "sum_bu_1_01_pboc_aa1_m12m": float(np.random.randint(50000, 5000000)),
            "agaa_zbvg_xavm_bbvf_mf": float(np.random.randint(-999, 3000)),
            "r12p24m_njslap_qtcnt": round(np.random.uniform(0, 1), 4),
        })

df = pd.DataFrame(data_rows)

# Inject some special missing values
for col in ["rat1_sum_bu_1_14_pboc_aj65_cur", "agaa_zbvg_xavm_bbvf_mf"]:
    mask = np.random.choice([True, False], size=len(df), p=[0.05, 0.95])
    df.loc[mask, col] = -999999.0

# ── Build more realistic mock scorecard ──
sc = MagicMock()
sc.get_var_names.return_value = [
    "txriskscorev7", "rat1_sum_bu_1_14_pboc_aj65_cur",
    "cu_ln_acct_lurate_gt50_arto", "r24m_cfcbnkndpst_noacct_ln_tac",
    "sum_bu_1_01_pboc_aa1_m12m", "agaa_zbvg_xavm_bbvf_mf",
    "r12p24m_njslap_qtcnt",
]

# IV table
iv_vals = [0.45, 0.32, 0.28, 0.21, 0.15, 0.09, 0.04]
sc.get_iv_table.return_value = pd.Series(
    iv_vals, index=sc.get_var_names.return_value
)
sc.get_ks_table.return_value = pd.Series(
    [0.38, 0.29, 0.25, 0.18, 0.12, 0.07, 0.03],
    index=sc.get_var_names.return_value,
)
sc.get_dropped_vars.return_value = []

# WOE tables with realistic structure
def _make_woe():
    return pd.DataFrame({
        "min": [-np.inf, 0.0, 10.0, 100.0],
        "max": [0.0, 10.0, 100.0, np.inf],
        "Good": [800, 1200, 600, 200],
        "Bad": [200, 100, 60, 40],
        "Total": [1000, 1300, 660, 240],
        "%Good": [0.29, 0.43, 0.21, 0.07],
        "%Bad": [0.50, 0.25, 0.15, 0.10],
        "%Total": [0.31, 0.41, 0.21, 0.07],
        "WoE": [-0.55, 0.54, 0.34, -0.36],
        "IV": [0.12, 0.10, 0.02, 0.08],
        "Bad Rate": [0.20, 0.08, 0.09, 0.17],
        "Lift": [1.25, 0.48, 0.56, 1.04],
    })

sc.get_woe_table = lambda var: _make_woe()
def _make_bins(var):
    return pd.Series([
        pd.Interval(-np.inf, 0.0), pd.Interval(0.0, 10.0),
        pd.Interval(10.0, 100.0), pd.Interval(100.0, np.inf),
    ], name="bins")

sc.get_bins = _make_bins

sc.get_model_summary.return_value = pd.DataFrame({
    "Parameter": ["intercept", "txriskscorev7", "rat1_sum_bu_1_14_pboc_aj65_cur",
                   "cu_ln_acct_lurate_gt50_arto", "r24m_cfcbnkndpst_noacct_ln_tac",
                   "sum_bu_1_01_pboc_aa1_m12m", "agaa_zbvg_xavm_bbvf_mf",
                   "r12p24m_njslap_qtcnt"],
    "Estimate": [-4.4828, -0.8293, -0.7891, -1.2238, -0.7081, -0.7372, -0.6836, -0.6256],
    "Std-Error": [0.0549, 0.0615, 0.0811, 0.2082, 0.1307, 0.1764, 0.1826, 0.1810],
    "Wald-Chi2": [6659.99, 181.55, 94.59, 34.56, 29.35, 17.47, 14.02, 11.94],
    "P-value": ["<.0001", "<.0001", "<.0001", "<.0001", "<.0001", "0.000029", "0.000181", "0.000550"],
    "P-value-num": [0.0, 0.0, 0.0, 0.0, 0.0, 0.000029, 0.000181, 0.000550],
    "Std": [0.0, 0.89, 0.48, 0.25, 0.38, 0.34, 0.47, 0.29],
    "Std-Estimate": [0.0, -0.4067, -0.2073, -0.1673, -0.1470, -0.1394, -0.1758, -0.0989],
    "VIF": [1.29, 1.10, 1.06, 1.13, 1.08, 1.23, 1.10, 1.02],
})

sc.get_scorecard.return_value = pd.DataFrame({
    "name": ["txriskscorev7"] * 4 + ["rat1_sum_bu_1_14_pboc_aj65_cur"] * 4,
    "left": [-np.inf, 0.0, 10.0, 100.0, -np.inf, 0.0, 10.0, 100.0],
    "right": [0.0, 10.0, 100.0, np.inf, 0.0, 10.0, 100.0, np.inf],
    "score": [25, 15, 8, 3, 20, 12, 6, 2],
}).set_index("name")

sc.get_missing_dict.return_value = {}

# ── Generate report ──
config = ReportConfig(
    partition_col="part_id",
    cust_col="cert_no",
    date_col="loan_date",
    target_col="mob6_30",
    flag_col="data_flag",
    score_col="pred_score",
    sc_score_col="scorecard_score",
)

gen = ReportGenerator(sc, config)
output_path = "/Users/lienming/ModelReport/sample_report.xlsx"
gen.to_excel(output_path, df)

print(f"Sample report generated: {output_path}")
print(f"Data shape: {df.shape}")
print(f"Data flags: {df['data_flag'].value_counts().to_dict()}")
print(f"Partitions: {sorted(df['part_id'].unique())}")
