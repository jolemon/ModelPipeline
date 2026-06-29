"""变量元数据加载（委托给 shared.metadata.loader）"""

from shared.metadata.loader import (
    load_metadata,
    is_feature_warehouse,
    load_feature_warehouse,
)

# 向后兼容：ModelReport 原有 API
load_variable_metadata = load_metadata
_is_feature_warehouse = is_feature_warehouse

# 向后兼容别名，新代码建议直接导入 shared.metadata.loader
__all__ = [
    "load_variable_metadata",
    "load_metadata",
    "is_feature_warehouse",
    "load_feature_warehouse",
]
