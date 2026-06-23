import logging
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)


def load_variable_metadata(path: Optional[str] = None) -> dict:
    """Load variable metadata from CSV/YAML/Excel file.

    Expected CSV columns: 变量名, 变量解释含义, 来源, 表描述

    Returns:
        dict mapping variable name → dict of metadata fields.
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
        if file_path.suffix in (".csv",):
            df = pd.read_csv(path)
        elif file_path.suffix in (".yaml", ".yml"):
            import yaml
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            df = pd.DataFrame(data)
        elif file_path.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            logger.warning("Unsupported metadata format: %s", file_path.suffix)
            return {}

        key_col = df.columns[0]
        df = df.set_index(key_col)
        return df.to_dict(orient="index")

    except Exception as e:
        logger.warning("Failed to load metadata from %s: %s", path, e)
        return {}
