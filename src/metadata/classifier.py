"""元数据包（P4重构）

职责：
    提供变量元数据的数据模型、加载、查询、分类、转换和分析功能。
    采用 Facade + 3 个子组件的架构模式。

架构关系：
    MetadataManager (metadata/manager.py) 作为 Facade，委托给 3 个专注子组件：

    ┌─────────────────────────────────────────┐
    │      MetadataManager (Facade)           │
    │    ~304行（原687行，P4重构后）           │
    │                                         │
    │  职责：加载、查询、分组、检测、统计        │
    └───────────────────┬─────────────────────┘
                        │ 委托给 3 个子组件
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   VariableClassifier  OverrideApplier  MetadataStatistics
   (变量分类/歧义解析)  (覆盖配置应用)    (统计报告生成)

组件说明：
    VariableClassifier:
        - 变量自动分类（征信/行为/外数/模型分）
        - 歧义变量解析（多表匹配时按 platform / behavior_platform_priority 选择）
        - 平台优先级处理

    OverrideApplier:
        - variable_overrides 配置应用（强制指定变量来源表）
        - table_join_keys 配置应用（覆盖关联键和分区字段）
        - 变量覆盖后的元数据更新

    MetadataStatistics:
        - 元数据画像生成（变量总数、表总数、平台分布）
        - 完整性统计（来源表完整率、描述完整率）
        - 特殊变量检测（跨表重复变量、疑似主键）
        - JSON 格式导出

数据模型：
    VariableMetadata (metadata/models.py): 单变量元数据
        - var_name, var_desc, source_table, category, platform
        - partition_field, join_key, db_column_name

    TableMetadata (metadata/models.py): 单表元数据
        - table_name, table_desc, category, platform
        - variables (变量列表), partition_field, join_key

工具函数：
    classify_category(): 根据表名推断变量分类
    classify_platform(): 根据表名推断平台
    infer_join_keys(): 根据表名和分类推断关联键
    convert_csv_to_yaml(): CSV 特征映射表转 YAML 元数据

缓存机制：
    首次加载 metadata.yaml 后自动生成同目录 .pkl 缓存，
    后续加载从缓存读取（速度提升约 90 倍），
    YAML 修改后自动检测并重建缓存。

使用方式：
    >>> from src.metadata import MetadataManager
    >>> metadata = MetadataManager()
    >>> metadata.load("config/metadata.yaml")  # 自动使用 .pkl 缓存
    >>> var_info = metadata.find_variable("cust_age")
    >>> metadata.print_statistics()
"""

from src.metadata.models import VariableMetadata, TableMetadata
from src.metadata.manager import MetadataManager
from src.metadata.variable_classifier import VariableClassifier
from src.metadata.override_applier import OverrideApplier
from src.metadata.metadata_statistics import MetadataStatistics
from src.metadata.classifier import classify_category, classify_platform, classify_fallback
from src.metadata.key_inference import (
    infer_join_keys,
    is_likely_key_field,
    LIKELY_KEY_FIELDS
)
from src.metadata.converter import convert_csv_to_yaml

__all__ = [
    'VariableMetadata',
    'TableMetadata',
    'MetadataManager',
    'VariableClassifier',
    'OverrideApplier',
    'MetadataStatistics',
    'classify_category',
    'classify_platform',
    'classify_fallback',
    'infer_join_keys',
    'is_likely_key_field',
    'LIKELY_KEY_FIELDS',
    'convert_csv_to_yaml'
]
