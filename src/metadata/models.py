"""
元数据数据模型定义

包含 VariableMetadata 和 TableMetadata 两个核心数据类，
被 metadata.manager 和其他模块共享使用。
"""

from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class VariableMetadata:
    """单个变量的元数据

    描述模型变量的完整元数据信息，包括变量名、来源表、分类、关联键等。
    被 MetadataManager 用于管理变量与表的映射关系。

    Attributes:
        var_name: 变量名（字段名），统一小写（与模型中的变量名一致）
        var_desc: 变量含义/描述
        source_table: 来源表名（如 'edap.v_BRDT_APPLYLOANSTR_md5'）
        table_desc: 表描述
        category: 变量分类（如 '征信变量'、'行为变量'、'外部数据'、'模型分'）
        platform: 平台二级分类（如 '百融'、'征信变量-消金'）
        partition_field: 分区字段（如 'dt'、'part_id'）
        join_key: 关联主键（如 'apply_no'、'cert_no'）
        join_key_candidates: 候选主键列表（当存在多个可能的主键时使用）
        is_duplicate: 是否跨表重复字段（同一变量名出现在多张表中）
        is_likely_key: 是否疑似主键/通用字段（如 cust_id, dt 等）
        db_column_name: 数据库实际列名（当与var_name不同时使用，用于别名映射）
    """
    var_name: str                    # 变量名（字段名），统一小写
    var_desc: str = ""               # 变量含义
    source_table: str = ""           # 来源表
    table_desc: str = ""             # 表描述
    category: str = ""               # 变量分类（征信变量/行为变量/外部数据/模型分）
    platform: str = ""               # 平台二级分类（百融/字节/征信变量-消金等）
    partition_field: str = ""        # 分区字段
    join_key: str = ""               # 关联主键（推荐）
    join_key_candidates: List[str] = field(default_factory=list)  # 候选主键列表
    is_duplicate: bool = False       # 是否跨表重复字段
    is_likely_key: bool = False      # 是否疑似主键/通用字段
    db_column_name: str = ""         # 数据库实际列名（当与var_name不同时使用）
    
    def __post_init__(self):
        """确保db_column_name默认等于var_name"""
        if not self.db_column_name:
            self.db_column_name = self.var_name
    
    def to_dict(self) -> dict:
        """将变量元数据转换为字典格式

        Returns:
            dict: 包含所有字段的字典表示
        """
        return asdict(self)


@dataclass
class TableMetadata:
    """单张表的元数据

    描述数据库表的结构信息，包括表名、分类、关联键、分区字段以及包含的变量列表。
    被 MetadataManager 用于管理变量与表的映射关系。

    Attributes:
        table_name: 表名（如 'edap.v_BRDT_APPLYLOANSTR_md5'）
        table_desc: 表描述（如 '百融多头变量'）
        category: 分类（如 '外部数据'、'征信变量'、'行为变量'、'模型分'）
        platform: 平台二级分类（如 '百融'、'征信变量-消金'）
        partition_field: 分区字段（如 'dt'、'part_id'）
        join_key: 关联主键（如 'apply_no'、'cert_no'、'ci_rpt_id'）
        join_key_candidates: 候选主键列表（当存在多个可能的主键时使用）
        variable_count: 变量数量（该表包含的变量总数）
        variables: 该表包含的变量名列表
    """
    table_name: str                  # 表名
    table_desc: str = ""             # 表描述
    category: str = ""               # 分类
    platform: str = ""               # 平台二级分类
    partition_field: str = ""        # 分区字段
    join_key: str = ""               # 关联主键（推荐）
    join_key_candidates: List[str] = field(default_factory=list)  # 候选主键列表
    variable_count: int = 0          # 变量数量
    variables: List[str] = field(default_factory=list)  # 该表包含的变量列表
