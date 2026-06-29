import logging
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd

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
        df["类型"] = df["来源表"].apply(_classify_category)
        df["平台"] = df["来源表"].apply(_classify_platform)
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


# ── Classification functions (from model_library/dataset_learn.py) ──

def _classify_category(table_name) -> str:
    """Classify feature category by source table name.

    Returns: 行为变量 / 外部数据 / 征信变量 / 模型分 / ""
    """
    if not table_name or not isinstance(table_name, str):
        return ""
    t = table_name.lower()
    if (t.startswith("wdyy.t_ccr") or t.startswith("wdyy.c01_ccr")
            or t.startswith("t_cc_cust") or t.startswith("wdyy.t_cc_cust")
            or t.startswith("ads.ads_risk_")):
        return "行为变量"
    if (t.startswith("edap.") or table_name == "jsbrpt.v_ods_02_all_zzxqsf_md5"
            or table_name in ("度小满", "京东", "腾讯", "天创", "友盟", "同盾")):
        return "外部数据"
    if (t.startswith("t_pbci") or t.startswith("wdyy.t_zxysblhs")
            or t.startswith("wdyy.v_md5_t_zxysblhs")
            or t.startswith("jsbrpt_mrs.zxbl_his")):
        return "征信变量"
    if t.startswith("sykj1.model"):
        return "模型分"
    return ""


def _classify_platform(table_name) -> str:
    """Classify feature platform by source table name.

    Returns: platform name (百融/字节/京东白条/etc.) or ""
    """
    if not table_name or not isinstance(table_name, str):
        return ""
    t = table_name.lower()
    if t.startswith("edap.v_br") or t.startswith("edap.v_fqz_br"):
        return "百融"
    if (t.startswith("wdyy.t_ccrdyyf") or t.startswith("wdyy.c01_ccrdyyf")
            or t.startswith("ned772")):
        return "字节"
    if t.startswith("wdyy.t_ccrbt"):
        return "京东白条"
    if table_name in ("度小满", "京东", "腾讯", "天创", "友盟", "同盾"):
        return table_name
    if table_name == "jsbrpt.v_ods_02_all_zzxqsf_md5":
        return "中征信"
    if t.startswith("ed0509"):
        return "天辰"
    if t.startswith("ned0535"):
        return "友盟"
    if t.startswith("ed0223"):
        return "度小满"
    if t.startswith("edap.") or t.startswith("ed"):
        return "外部数据"
    if t.startswith("ads.ads_risk_"):
        return "贷中行为变量-新底座"
    if table_name == "wdyy.T_CC_CUST_BEHAV_VARBL_INDEX":
        return "行为变量-消金"
    if t.startswith("t_cc_cust") or t.startswith("wdyy.t_cc_cust"):
        return "行为变量-总行"
    if (t.startswith("wdyy.t_zxysblhs") or t.startswith("wdyy.v_md5_t_zxysblhs")
            or t.startswith("jsbrpt_mrs.zxbl_his")):
        return "征信变量-消金"
    if t.startswith("t_pbci"):
        return "征信变量-总行"
    return ""
