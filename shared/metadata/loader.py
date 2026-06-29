"""
统一元数据加载器

合并 ModelVarDiff 和 ModelReport 的特征仓库读取逻辑，
提供单一入口处理 CSV/Excel 格式的特征映射表。

使用示例:
    # ModelVarDiff 风格：返回 DataFrame
    df = load_feature_warehouse("特征映射表.xlsx")
    df = load_feature_warehouse("特征映射表.xlsx", compose_source=True)

    # ModelReport 风格：返回 {var_name: {含义, 来源, 表描述}}
    meta = load_metadata("vars.csv")
    meta = load_metadata("vars.csv", classify=True)
"""

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 特征仓库默认路径（来自 shared.model_library.config）
FEATURE_WAREHOUSE_DEFAULT = "/srv/data_warehouse/特征映射表.xlsx"


def is_feature_warehouse(df: pd.DataFrame) -> bool:
    """检测 DataFrame 是否为特征仓库格式。

    特征仓库必须包含 字段名 列，以及 来源表 或 字段含义 列。

    Args:
        df: 输入 DataFrame

    Returns:
        True 表示是特征仓库格式
    """
    cols = [str(c) for c in df.columns]
    return "字段名" in cols and ("来源表" in cols or "字段含义" in cols)


def load_feature_warehouse(
    path: Optional[str] = None,
    compose_source: bool = True,
    normalize_names: bool = True,
) -> Optional[pd.DataFrame]:
    """加载特征映射表并做归一化处理。

    覆盖 ModelVarDiff 的 _load_feature_warehouse + ModelReport 的文件读取逻辑。

    Args:
        path: 文件路径。若为 None，尝试从默认路径加载。
        compose_source: 若 True，当有 库名+表名 列时自动拼接为 来源表 列。
        normalize_names: 若 True，将 字段名 列转为小写。

    Returns:
        DataFrame，若文件不存在或格式不符则返回 None
    """
    # 解析路径
    file_path = _resolve_path(path)
    if file_path is None:
        return None

    # 读取文件
    df = _read_file(file_path)
    if df is None:
        return None

    # 验证格式
    if "字段名" not in df.columns:
        logger.warning("文件缺少「字段名」列，不是有效的特征映射表: %s", file_path)
        return None

    # 归一化
    if normalize_names:
        df = df.copy()
        df["字段名"] = df["字段名"].astype(str).str.lower()

    # 来源表拼接
    if compose_source and "来源表" not in df.columns:
        if "库名" in df.columns and "表名" in df.columns:
            df = df.copy()
            df["来源表"] = df["库名"].astype(str) + "." + df["表名"].astype(str)
        else:
            logger.warning("文件无「来源表」列，且无法从「库名.表名」拼接: %s", file_path)
            return None

    return df


def load_metadata(
    path: Optional[str] = None,
    classify: bool = True,
) -> dict:
    """加载变量元数据并返回 {变量名: {含义, 来源, 表描述}} 字典。

    覆盖 ModelReport 的 load_variable_metadata + _parse_feature_warehouse。

    Args:
        path: 文件路径。支持 CSV/Excel/YAML。
        classify: 若 True，对特征仓库格式自动应用分类（类别+平台）。

    Returns:
        {var_name: {变量解释含义, 来源, 表描述}} 字典。文件不存在时返回空字典。
    """
    if path is None:
        return {}

    file_path = Path(path)
    if not file_path.exists():
        logger.warning("元数据文件不存在: %s", path)
        return {}

    try:
        df = _read_file(file_path)
        if df is None:
            return {}

        # 自动检测特征仓库格式
        if is_feature_warehouse(df):
            return _parse_feature_warehouse(df, classify=classify)

        # 通用格式：第一列作为 key
        key_col = df.columns[0]
        df = df.set_index(key_col)
        return df.to_dict(orient="index")

    except Exception as e:
        logger.warning("加载元数据失败 (%s): %s", path, e)
        return {}


def lookup_source(
    warehouse: Optional[pd.DataFrame],
    var_name: str,
) -> str:
    """在特征仓库中查找变量的来源表。

    覆盖 ModelVarDiff 的 _lookup_source。

    Args:
        warehouse: load_feature_warehouse() 返回的 DataFrame
        var_name: 变量名

    Returns:
        来源表名，未找到时返回 "unknown"
    """
    if warehouse is None:
        return "unknown"
    match = warehouse[warehouse["字段名"] == var_name.lower()]
    if len(match) > 0:
        return str(match.iloc[0]["来源表"])
    return "unknown"


# ── 内部函数 ──────────────────────────────────────────────────────

def _resolve_path(explicit: Optional[str]) -> Optional[Path]:
    """解析路径：explicit > 默认路径 > None"""
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
    # 尝试默认路径
    if os.path.exists(FEATURE_WAREHOUSE_DEFAULT):
        return Path(FEATURE_WAREHOUSE_DEFAULT)
    return None


def _read_file(file_path: Path) -> Optional[pd.DataFrame]:
    """根据后缀读取文件"""
    suffix = file_path.suffix.lower()
    try:
        if suffix in (".xlsx", ".xls"):
            return pd.read_excel(file_path)
        elif suffix == ".csv":
            # 自动检测分隔符
            return pd.read_csv(file_path, sep=None, engine="python")
        elif suffix in (".yaml", ".yml"):
            import yaml
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
            return pd.DataFrame(data)
        else:
            logger.warning("不支持的文件格式: %s", suffix)
            return None
    except Exception as e:
        logger.warning("读取文件失败 (%s): %s", file_path, e)
        return None


def _parse_feature_warehouse(df: pd.DataFrame, classify: bool = True) -> dict:
    """将特征仓库 DataFrame 转换为 {变量名: info} 字典。"""
    from shared.metadata.classifier import classify_category, classify_platform

    df = df.copy()
    df["字段名"] = df["字段名"].astype(str).str.lower()

    if classify and "来源表" in df.columns:
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

        category = str(row.get("类型", "")) if pd.notna(row.get("类型", np.nan)) else ""
        platform = str(row.get("平台", "")) if pd.notna(row.get("平台", np.nan)) else ""
        desc = "-".join(filter(None, [category, platform])) if category or platform else ""

        result[var_name] = {
            "变量解释含义": meaning,
            "来源": source,
            "表描述": desc,
        }

    return result
