import logging
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd

from shared.classifier import classify_category, classify_platform

logger = logging.getLogger(__name__)


def load_variable_metadata(path: Optional[str] = None) -> dict:
    """Load variable metadata from CSV/YAML/Excel file.

    If the file is a feature warehouse Excel (has 字段名/来源表 columns),
    auto-classification logic from dataset_learn.py is applied.
    Otherwise, generic column mapping is used.

    Returns:
        dict mapping variable name → dict with keys: 变量解释含义, 来源, 表描述.
        Returns empty dict if file not found or path is None.
    """
    if path is None:
        return {}

    file_path = Path(path)
    if not file_path.exists():
        logger.warning("Variable metadata file not found: %s, "
                       "filling metadata columns with empty strings.", path)
        return {}

    try:
        if file_path.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        elif file_path.suffix in (".csv",):
            df = pd.read_csv(path)
        elif file_path.suffix in (".yaml", ".yml"):
            import yaml
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            df = pd.DataFrame(data)
        else:
            logger.warning("Unsupported metadata format: %s", file_path.suffix)
            return {}

        # Auto-detect: feature warehouse format
        if _is_feature_warehouse(df):
            return _parse_feature_warehouse(df)

        # Generic format: first column is key
        key_col = df.columns[0]
        df = df.set_index(key_col)
        return df.to_dict(orient="index")

    except Exception as e:
        logger.warning("Failed to load metadata from %s: %s", path, e)
        return {}


def _is_feature_warehouse(df: pd.DataFrame) -> bool:
    """Check if DataFrame looks like a feature warehouse Excel."""
    cols = [str(c) for c in df.columns]
    return "字段名" in cols and ("来源表" in cols or "字段含义" in cols)


def _parse_feature_warehouse(df: pd.DataFrame) -> dict:
    """Parse feature warehouse Excel into metadata dict with auto-classification.

    Feature warehouse columns: 字段名, 来源表, 字段含义, ...
    Output: {var_name: {变量解释含义: ..., 来源: ..., 表描述: ...}}
    """
    df = df.copy()
    df["字段名"] = df["字段名"].astype(str).str.lower()

    # Apply classification
    if "来源表" in df.columns:
        df["类型"] = df["来源表"].apply(classify_category)
        df["平台"] = df["来源表"].apply(classify_platform)
    else:
        df["类型"] = ""
        df["平台"] = ""

    result = {}
    for _, row in df.iterrows():
        var_name = str(row["字段名"])
        meaning = str(row.get("字段含义", "")) if pd.notna(row.get("字段含义", np.nan)) else ""
        source = str(row.get("来源表", "")) if "来源表" in df.columns and pd.notna(row.get("来源表", np.nan)) else ""

        # Build 表描述 from 类型 and 平台
        category = str(row.get("类型", "")) if pd.notna(row.get("类型", np.nan)) else ""
        platform = str(row.get("平台", "")) if pd.notna(row.get("平台", np.nan)) else ""
        desc = "-".join(filter(None, [category, platform])) if category or platform else ""

        result[var_name] = {
            "变量解释含义": meaning,
            "来源": source,
            "表描述": desc,
        }

    return result
