"""
SQL 构建数据模型模块

定义 SQLBuilder 和 JoinPlanner 共享的核心数据结构：
- TableGroup: 临时表分组（同 platform + join_key 的表集合）
- JoinPlan: JOIN 执行计划
- OutputConfig: 输出表配置
"""

from typing import List, Dict, Set, Union
from dataclasses import dataclass, field


@dataclass
class TableGroup:
    """临时表分组（同platform+join_key的表集合）

    在JOIN规划阶段，将具有相同平台（platform）和关联键（join_key）的表
    划分为一个分组，生成一个CTE或临时表。这样可以减少最终JOIN的复杂度。

    Attributes:
        group_id: 分组标识（英文），如 "credit_xj_ci_rpt_id_001"
        platform: 平台名称（中文，用于注释）
        platform_en: 平台名称（英文，用于命名）
        join_key: 关联键（如 'apply_no', 'ci_rpt_id'）
        tables: 该分组包含的源表名列表
        table_vars: 每张表对应的变量列表 {table_name: [var_name, ...]}
        all_variables: 去重后的全部变量名列表
        duplicate_vars: 组内重复变量集合（同名但不同表）
        seq: 分组序号（用于生成唯一临时表名）
        temp_table_name: 完整临时表名称（由SQLConfig生成）
    """
    group_id: str                      # 分组标识（英文），如 "credit_xj_ci_rpt_id_001"
    platform: str                      # 平台名称（中文，用于注释）
    platform_en: str                   # 平台名称（英文，用于命名）
    join_key: str                      # 关联键
    tables: List[str] = field(default_factory=list)           # 表名列表
    table_vars: Dict[str, List[str]] = field(default_factory=dict)  # {table: [vars]}
    all_variables: List[str] = field(default_factory=list)    # 去重后的全部变量
    duplicate_vars: Set[str] = field(default_factory=set)     # 组内重复变量
    seq: int = 1                       # 分组序号（用于命名）
    temp_table_name: str = ""          # 完整临时表名称（由SQLConfig生成）

    def __post_init__(self):
        """确保temp_table_name有默认值（兼容旧格式，但优先使用外部传入值）"""
        if not self.temp_table_name:
            self.temp_table_name = (
                f"tmp_{self.platform_en}_{self.join_key}_{self.seq:03d}"
            )


@dataclass
class JoinPlan:
    """JOIN执行计划

    描述从样本表到各变量表的完整关联策略，包括样本表信息、
    各CTE分组以及样本表到各分组的桥接字段映射。

    Attributes:
        sample_table: 样本表名（如 'dwd_apply_info'）
        sample_alias: 样本表别名（如 's'），从表名自动推断
        sample_key: 样本表主键（如 'apply_no'）
        sample_fields: 样本表保留字段列表（除主键外）
        groups: CTE/临时表分组列表（每个分组对应一个子查询）
        bridge_keys: 样本表到各分组的桥接字段映射 {group_id: bridge_key}
                     bridge_key 是样本表中用于关联到该分组的字段，
                     如 cust_no, ci_rpt_id, cert_no
    """
    sample_table: str                  # 样本表名
    sample_key: str                    # 样本表主键（如 apply_no）
    sample_alias: str = "s"            # 样本表别名（从表名推断）
    sample_fields: List[str] = field(default_factory=list)    # 样本表保留字段
    groups: List[TableGroup] = field(default_factory=list)    # CTE分组列表
    bridge_keys: Dict[str, str] = field(default_factory=dict) # {group_id: bridge_key}
    # bridge_key 是样本表到CTE的关联字段，如 cust_no, ci_rpt_id, cert_no


@dataclass
class OutputConfig:
    """输出表配置

    定义最终输出表的结构信息，包括表名、数据库、分区语句和空值填充策略。

    Attributes:
        output_table: 输出表名
        output_db: 输出数据库名（如为空则不添加数据库前缀）
        partition_clause: 分区语句（如 'PARTITION (dt=${biz_date})'）
        coalesce_value: 空值填充值，默认 -999999（用于LEFT JOIN时填充缺失值）
    """
    output_table: str = ""             # 输出表名
    output_db: str = ""                # 输出数据库
    partition_clause: str = ""         # 分区语句
    coalesce_value: Union[int, float] = -999999  # 空值填充值
