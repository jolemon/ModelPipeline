"""
核心模块包

提供项目的基础核心功能：
- 配置加载 (config_loader)
- 特征提取 (lgb_feature_extractor)
- 元数据管理 (metadata_manager)
- SQL生成 (lgb2sql, sql_builder, join_planner, models)
"""

from src.core.config_loader import SQLConfig
from src.core.lgb_feature_extractor import LgbFeatureExtractor
from src.metadata.manager import MetadataManager
from src.metadata.models import VariableMetadata, TableMetadata
from src.core.lgb2sql import Lgb2Sql
from src.core.models import TableGroup, JoinPlan, OutputConfig
from src.core.join_planner import JoinPlanner
from src.core.sql_builder import SQLBuilder

__all__ = [
    'SQLConfig',
    'LgbFeatureExtractor',
    'MetadataManager',
    'VariableMetadata',
    'TableMetadata',
    'Lgb2Sql',
    'SQLBuilder',
    'JoinPlanner',
    'TableGroup',
    'JoinPlan',
    'OutputConfig'
]
