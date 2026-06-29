"""Pipeline Stage 子模块（P2重构提取）

职责：
    将 LgbToSqlPipeline 的任务流执行职责按步骤拆分为 5 个专注的 Stage 类，
    每个 Stage 只负责一个明确的处理步骤，通过 PipelineContext 共享状态。

架构关系：
    LgbToSqlPipeline (pipeline_pkg/pipeline_core.py) 作为 Facade，
    按顺序调用本模块的 5 个 Stage：

    ┌─────────────────────────────────────────┐
    │    LgbToSqlPipeline (Facade)            │
    │    ~280行（原661行，P2重构后）           │
    │                                         │
    │  职责：任务流编排、错误处理、结果汇总      │
    └───────────────────┬─────────────────────┘
                        │ 按顺序调用 5 个 Stage
        ┌───────────────┼───────────────┬───────────────┐
        ▼               ▼               ▼               ▼
   ConfigStage   FeatureExtractionStage  MetadataReportStage
   (配置初始化)    (模型解析/提取变量)     (查询元数据/生成报告)
                                                        │
                        ┌───────────────────────────────┘
                        ▼
              SQLGenerationStage    ScoreGenerationStage
              (生成 JOIN SQL)        (生成打分SQL)
                        │                    │
                        └────────┬───────────┘
                                 ▼
                          PipelineContext
                          (跨Stage共享状态)

Stage 说明：
    ConfigStage:
        - 加载配置文件（SQLConfig）
        - 加载元数据（MetadataManager）
        - 初始化模型加载器
        - 准备 PipelineContext

    FeatureExtractionStage:
        - 解析模型文件（.pkl / .pmml / .model）
        - 提取入模变量列表
        - 过滤零重要度变量
        - 检查禁用变量黑名单命中情况

    MetadataReportStage:
        - 查询每个入模变量的元数据
        - 分类统计：正常命中 / 未命中 / 歧义变量
        - 生成控制台报告和 Markdown 报告
        - 应用变量覆盖配置

    SQLGenerationStage:
        - 调用 JoinPlanner 规划 JOIN 策略
        - 调用 SQLBuilder 生成变量拼接 SQL
        - 支持 CTE 和临时表两种模式
        - 保存 SQL 到文件

    ScoreGenerationStage:
        - 调用 ScoreGenerator 生成打分 SQL
        - 空值填充（NVL → coalesce_value）
        - 全空样本标记（all_null_flag）
        - sigmoid 概率计算
        - 评分卡映射（log-odds 转换）

    PipelineContext:
        - 跨 Stage 共享的数据容器
        - 存储：config、metadata、model_features、join_sql、score_sql 等
        - 避免 Stage 之间直接耦合

使用方式：
    通常不直接调用 Stage，而是通过 LgbToSqlPipeline Facade 使用：

    >>> from src.pipeline_pkg import LgbToSqlPipeline
    >>> pipeline = LgbToSqlPipeline(config_path="config/config.yaml")
    >>> result = pipeline.run(model_path="input/model.model")

    如需单独使用某个 Stage（如测试场景）：

    >>> from src.pipeline_pkg.stages import ConfigStage, PipelineContext
    >>> ctx = PipelineContext()
    >>> ConfigStage(ctx).execute(config_path="config/config.yaml")
"""

from .context import PipelineContext
from .config_stage import ConfigStage
from .feature_stage import FeatureExtractionStage
from .metadata_stage import MetadataReportStage
from .sql_stage import SQLGenerationStage
from .score_stage import ScoreGenerationStage

__all__ = [
    'PipelineContext',
    'ConfigStage',
    'FeatureExtractionStage',
    'MetadataReportStage',
    'SQLGenerationStage',
    'ScoreGenerationStage',
]
