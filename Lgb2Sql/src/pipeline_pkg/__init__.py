"""
任务流包

提供 LightGBM 模型到 Hive SQL 的完整转换任务流。
"""

# 延迟导入以避免循环导入问题
# 各子模块通过显式导入路径访问，如:
#   from src.pipeline_pkg.pipeline_core import LgbToSqlPipeline
#   from src.pipeline_pkg.scorer import ScoreGenerator

__all__ = [
    'LgbToSqlPipeline',
    'PipelineError',
    'run_pipeline',
    'FeatureReporter',
    'ScoreGenerator',
    'MarkdownReporter',
    'SQL_FULL',
]
