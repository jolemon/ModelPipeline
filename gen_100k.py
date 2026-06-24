"""Generate 100k synthetic samples and model report."""
import pandas as pd
import numpy as np
from model_report import ReportGenerator, ReportConfig

np.random.seed(42)
n = 100_000

# ── Generate data ──
# target: 2% bad rate
target = np.random.choice([0, 1], n, p=[0.98, 0.02])

# scorecard_score: higher = better (less likely to be bad)
# Goods: mean 700, std 80. Bads: mean 500, std 100
goods_score = np.random.normal(700, 80, n)
bads_score = np.random.normal(500, 100, n)
sc_score = np.where(target == 0, goods_score, bads_score)
sc_score = np.clip(sc_score, 300, 900).astype(int)

# pred_score (0-1): inverse of scorecard, higher = riskier
pred = 1 - (sc_score - 300) / 600
pred = np.clip(pred, 0.001, 0.999)

# date: spread over 12 months
months = [f"2025{m:02d}" for m in range(1, 13)]
dates = np.random.choice(months, n)
loan_dates = [f"{m[:4]}-{m[4:]}-15" for m in dates]

# Split: 60% train, 15% test, 20% oot, 5% oos
flags = np.random.choice(
    ["train", "test", "oot", "oos"], n,
    p=[0.60, 0.15, 0.20, 0.05]
)

# Features: 8 random features with varying predictive power
feat_cols = {
    "txriskscorev7": target * 0.3 + np.random.normal(0, 1, n),           # correlated with target
    "l3m_cnsmcnt_sum": np.random.exponential(5, n),                        # consumption count
    "l24m_bal_add_ms": np.random.randint(0, 24, n).astype(float),          # balance months
    "cu_ln_acct_lurate_gt50_arto": np.random.beta(2, 8, n),                # loan utilization
    "r24m_cfcbnkndpst_noacct_ln_tac": np.random.choice([0, 1, 2, 3], n),  # no-account loans
    "sum_bu_1_01_pboc_aa1_m12m": np.random.lognormal(12, 1.5, n),         # PBOC query amount
    "agaa_zbvg_xavm_bbvf_mf": np.random.normal(500, 300, n),              # some behavioral var
    "r12p24m_njslap_qtcnt": np.random.uniform(0, 1, n),                   # some ratio
}

# Inject 3% special missing values into some columns
for col in ["r24m_cfcbnkndpst_noacct_ln_tac", "agaa_zbvg_xavm_bbvf_mf"]:
    mask = np.random.choice([True, False], n, p=[0.03, 0.97])
    feat_cols[col][mask] = -999999.0

# Loan amount for amount-weighted metrics
loan_amount = np.random.lognormal(9, 0.8, n)  # median ~8000

df = pd.DataFrame({
    "part_id": dates,
    "cert_no": [f"id_{i:08d}" for i in range(n)],
    "loan_date": loan_dates,
    "mob6_30": target,
    "data_flag": flags,
    "pred_score": pred,
    "scorecard_score": sc_score,
    "loan_amount": loan_amount,
    **feat_cols,
})

print(f"Data: {df.shape}")
print(f"  Train: {(df.data_flag=='train').sum()}, Test: {(df.data_flag=='test').sum()}, OOT: {(df.data_flag=='oot').sum()}, OOS: {(df.data_flag=='oos').sum()}")
print(f"  Bad rate: {df.mob6_30.mean():.2%}")
print(f"  Score range: {df.scorecard_score.min()}-{df.scorecard_score.max()}")

# ── Generate report ──
config = ReportConfig(
    partition_col="part_id",
    cust_col="cert_no",
    date_col="loan_date",
    target_col="mob6_30",
    flag_col="data_flag",
    score_col="pred_score",
    sc_score_col="scorecard_score",
    loan_amount_col="loan_amount",
    exclude_columns=["pred_score"],
)

print("\nGenerating report...")
gen = ReportGenerator(None, config)
gen.to_excel("report_100k.xlsx", df)
print("Done: report_100k.xlsx")
