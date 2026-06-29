"""SQL构建子模块（P1重构提取）

职责：
    将 SQLBuilder 的 SQL 生成职责拆分为 5 个专注的子组件，
    每个类只负责一个明确的 SQL 生成子任务。

架构关系：
    SQLBuilder (core/sql_builder.py) 作为 Facade，初始化并委托给本模块的 5 个组件：

    ┌─────────────────────────────────────────┐
    │         SQLBuilder (Facade)             │
    │    ~320行（原1295行，P1重构后）          │
    └───────────────────┬─────────────────────┘
                        │ 委托给 5 个子组件
        ┌───────────────┼───────────────┬───────────────┐
        ▼               ▼               ▼               ▼
   FieldCollector  SubqueryBuilder  CreditGroupHandler  MergeTableBuilder
   (字段收集)       (子查询构建)      (征信分组处理)       (合并表构建)
        │               │               │               │
        └───────────────┴───────────────┴───────────────┘
                                    │
                                    ▼
                            SQLFormatter
                            (SQL格式化与输出)

组件说明：
    FieldCollector:
        - 变量到数据库列名的映射（含 variable_aliases 处理）
        - 按平台/分类收集 SELECT 字段
        - 跨表重复变量检测与重命名（添加表别名前缀）

    SubqueryBuilder:
        - 单表子查询生成（含 WHERE 分区条件、IN 子查询）
        - 多表 JOIN 子查询生成（含 ON 条件构建）
        - CTE（WITH）构造
        - 样本表 CTE 和分组 CTE 构建

    CreditGroupHandler:
        - 征信组检测（基于 credit_platforms 配置）
        - 征信桥接表 SQL 生成（样本表 cert_no → ci_rpt_id）
        - 征信临时表生成（带时间窗口和 MD5 转换）

    MergeTableBuilder:
        - 组内合并临时表 SQL 生成（group_merge 功能）
        - 合并表映射关系维护

    SQLFormatter:
        - 最终 SELECT 语句组装
        - 最终 JOIN 语句组装
        - SQL 缩进格式化
        - 文件保存与执行摘要生成

使用方式：
    通常不直接实例化这些类，而是通过 SQLBuilder Facade 使用：

    >>> from src.core.sql_builder import SQLBuilder
    >>> builder = SQLBuilder(metadata_manager, sql_config)
    >>> sql = builder.build_temp_table_sql(model_features, sample_config, output_config)

    如需单独使用某个组件（如测试场景）：

    >>> from src.core.sql import FieldCollector
    >>> collector = FieldCollector(metadata_manager, sql_config)
    >>> fields = collector.collect_select_fields(table_group)
"""

from .field_collector import FieldCollector
from .subquery_builder import SubqueryBuilder
from .credit_group_handler import CreditGroupHandler
from .merge_table_builder import MergeTableBuilder
from .sql_formatter import SQLFormatter

__all__ = [
    'FieldCollector',
    'SubqueryBuilder',
    'CreditGroupHandler',
    'MergeTableBuilder',
    'SQLFormatter',
]
