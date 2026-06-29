"""
共享元数据模块

提供特征映射表/特征仓库的加载、变量查询、分类等跨项目通用功能。

核心功能:
    load_feature_warehouse()  — 加载特征映射表（CSV/Excel），自动归一化
    load_metadata()           — 加载元数据并返回 {var_name: info} 字典
    classify_category()       — 表名 → 变量大类
    classify_platform()       — 表名 → 数据平台
"""

from shared.metadata.classifier import (
    classify_category,
    classify_platform,
    classify_fallback,
)
from shared.metadata.loader import (
    load_feature_warehouse,
    load_metadata,
    is_feature_warehouse,
)

__all__ = [
    'classify_category',
    'classify_platform',
    'classify_fallback',
    'load_feature_warehouse',
    'load_metadata',
    'is_feature_warehouse',
]
