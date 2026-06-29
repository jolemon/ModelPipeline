"""
共享工具函数

提供缺失值判定、缺失率计算、日期转换等跨项目通用功能。
三个项目统一使用此模块，确保行为一致。
"""

import numpy as np
import pandas as pd

# ── 缺失值 ──────────────────────────────────────────────────────

# 业务约定：数值 <= -99999 视为缺失值哨兵
MISSING_THRESHOLD = -99999


def is_missing(series: pd.Series) -> pd.Series:
    """检查缺失值：NaN、空字符串、或取值 <= MISSING_THRESHOLD。

    Args:
        series: 输入 Series

    Returns:
        布尔 Series，True 表示缺失
    """
    null_mask = series.isna()
    if series.dtype == object:
        str_col = series.astype(str).str.strip()
        null_mask = null_mask | (str_col == "") | (str_col == "nan") | (str_col == "NaN")
    numeric_series = pd.to_numeric(series, errors="coerce")
    null_mask = null_mask | (numeric_series <= MISSING_THRESHOLD)
    return null_mask


def calc_missing_rate(series: pd.Series, threshold: float = MISSING_THRESHOLD) -> float:
    """计算缺失率：NaN 和 <= threshold 的视为缺失。

    内部调用 is_missing，与 Comparator 的缺失判定完全一致。

    Args:
        series: 输入 Series
        threshold: 缺失值阈值，默认 MISSING_THRESHOLD

    Returns:
        缺失率 (0.0 ~ 1.0)
    """
    total = len(series)
    if total == 0:
        return 0.0
    missing_count = is_missing(series).sum()
    return float(missing_count / total)


# ── 日期 ─────────────────────────────────────────────────────────

def to_month(series: pd.Series) -> pd.Series:
    """将日期 Series 转换为 yyyyMM 字符串。

    例如: 2025-01-06 → 202501

    Args:
        series: 日期 Series

    Returns:
        yyyyMM 格式字符串 Series
    """
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y%m")
