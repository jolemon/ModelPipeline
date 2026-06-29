"""配置子模块包（P3重构提取）

职责：
    将 SQLConfig 的配置解析职责按领域拆分为 6 个专注的子配置类，
    每个类只负责一个明确的配置领域。

架构关系：
    SQLConfig (core/config_loader.py) 作为 Facade，初始化并委托给本模块的 6 个子类：

    ┌─────────────────────────────────────────┐
    │          SQLConfig (Facade)             │
    │    ~275行（原891行，P3重构后）           │
    └───────────────────┬─────────────────────┘
                        │ 委托给 6 个子配置类
        ┌───────────────┼───────────────┬───────────────┐
        ▼               ▼               ▼               ▼
   ProjectConfig  SQLGenerationConfig  OutputConfig  PipelineConfig
   (项目信息)      (SQL生成参数)        (输出配置)     (流水线配置)
                        │
                        ├─────────────────┐
                        ▼                 ▼
                  OverrideConfig    CreditBridgeConfig
                  (覆盖+别名+黑名单)   (征信桥接配置)

子配置类说明：
    ProjectConfig:
        - 项目基本信息：work_no、model_id、model_file_id、product_code
        - 临时表命名工具：根据命名规则生成 tmp_{work_no}_{date}_{model_id}_{type}_{seq}
        - 变量替换：${work_no}、${model_id}、${product_code} 等占位符解析

    SQLGenerationConfig:
        - SQL 生成参数：max_subquery_join、coalesce_value、partition_field
        - JOIN 类型配置：by_category / by_platform
        - 分区控制策略：partition_control（default / by_category / by_platform / by_table）
        - 征信平台识别：credit_platforms
        - 组内合并开关：group_merge

    OutputConfig:
        - 输出表配置：table_name、database、partition_clause
        - 样本表配置：保留字段、是否包含样本字段
        - 变量输出控制：enabled、sort_by_importance、top_n

    PipelineConfig:
        - 流水线执行模式：mode（temp_table / cte）
        - SQL 保存路径：save_sql
        - 报告保存路径：save_report
        - 打分开关：generate_score

    OverrideConfig:
        - 变量覆盖：variable_overrides（强制指定来源表）
        - 变量别名：variable_aliases（模型名→数据库列名映射）
        - 禁用变量黑名单：blacklist_vars + blacklist_file（合并生效）

    CreditBridgeConfig:
        - 征信桥接表配置解析：enabled、table_name、primary_key
        - 时间窗口参数：time_window_days、direction
        - MD5 转换开关：md5_transform

使用方式：
    通常不直接实例化这些类，而是通过 SQLConfig Facade 使用：

    >>> from src.core.config_loader import SQLConfig
    >>> config = SQLConfig("config/config.yaml")
    >>> print(config.work_no)           # ProjectConfig 委托
    >>> print(config.max_subquery_join) # SQLGenerationConfig 委托
    >>> print(config.blacklist_vars)    # OverrideConfig 委托

    如需单独使用某个子配置类（如测试场景）：

    >>> from src.core.config import ProjectConfig
    >>> proj = ProjectConfig(config_dict)
    >>> table_name = proj.generate_temp_table_name("pbci", 1)
"""

from .project_config import ProjectConfig
from .sql_generation_config import SQLGenerationConfig
from .output_config import OutputConfig
from .pipeline_config import PipelineConfig
from .override_config import OverrideConfig
from .credit_bridge_config import CreditBridgeConfig

__all__ = [
    'ProjectConfig',
    'SQLGenerationConfig',
    'OutputConfig',
    'PipelineConfig',
    'OverrideConfig',
    'CreditBridgeConfig',
]
