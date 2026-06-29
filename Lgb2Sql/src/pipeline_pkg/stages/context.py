"""
Pipeline 上下文模块

职责：在 Stage 之间传递状态和配置组件引用
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class PipelineContext:
    """流水线上下文数据容器

    包含所有 Stage 共享的配置组件和中间状态。
    各 Stage 通过读写 Context 传递数据，避免直接耦合。
    """

    # ========== 组件（由 ConfigStage 初始化）==========
    config: Optional[Any] = None
    metadata: Optional[Any] = None
    sql_builder: Optional[Any] = None
    feature_reporter: Optional[Any] = None
    score_generator: Optional[Any] = None
    markdown_reporter: Optional[Any] = None

    # ========== 状态（由各 Stage 传递）==========
    features: List[str] = field(default_factory=list)
    feature_meta: Dict[str, Any] = field(default_factory=dict)
    zero_importance_features: List[str] = field(default_factory=list)
    join_sql: str = ""
    score_sql: Optional[str] = None
    join_plan: Optional[Any] = None
    model_info: Dict[str, Any] = field(default_factory=dict)
