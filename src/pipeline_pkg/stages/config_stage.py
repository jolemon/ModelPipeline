"""
配置初始化 Stage

职责：加载配置、加载元数据、应用覆盖配置、初始化所有下游组件
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config_loader import SQLConfig
from src.metadata.manager import MetadataManager
from src.core.sql_builder import SQLBuilder
from src.pipeline_pkg.feature_reporter import FeatureReporter
from src.pipeline_pkg.scorer import ScoreGenerator
from src.pipeline_pkg.markdown_reporter import MarkdownReporter


class ConfigStage:
    """配置初始化 Stage：加载配置和元数据，初始化所有组件"""

    def execute(self, ctx,
                config_path: Optional[str] = None,
                metadata_path: Optional[str] = None,
                model_config_path: Optional[str] = None) -> None:
        """执行配置初始化

        Args:
            ctx: PipelineContext
            config_path: 配置文件路径
            metadata_path: 元数据文件路径
            model_config_path: 模型专属配置路径
        """
        # 1. 加载配置
        ctx.config = SQLConfig(config_path, model_config_path)

        # 2. 加载元数据
        ctx.metadata = MetadataManager(metadata_path)
        if metadata_path is None:
            default_meta = Path(__file__).resolve().parent.parent.parent.parent / "config" / "metadata.yaml"
            if default_meta.exists():
                ctx.metadata.load(default_meta)
            else:
                from src.pipeline_pkg.pipeline_core import PipelineError
                raise PipelineError(f"默认元数据文件不存在: {default_meta}，请指定metadata_path")
        else:
            ctx.metadata.load(metadata_path)

        # 3. 应用覆盖配置
        if ctx.config.variable_overrides:
            ctx.metadata.apply_variable_overrides(
                ctx.config.variable_overrides,
                table_join_keys=ctx.config.table_join_keys
            )

        if ctx.config.table_join_keys:
            print("\n[应用表关联键覆盖配置]")
            ctx.metadata.apply_table_join_key_overrides(ctx.config.table_join_keys)

        if ctx.config.variable_aliases:
            print("\n[应用变量名别名映射]")
            ctx.metadata.apply_variable_aliases(ctx.config.variable_aliases)

        # 4. 初始化下游组件
        ctx.sql_builder = SQLBuilder(ctx.metadata, ctx.config)
        ctx.feature_reporter = FeatureReporter(ctx.metadata, ctx.config)
        ctx.score_generator = ScoreGenerator(ctx.config)
        ctx.markdown_reporter = MarkdownReporter(ctx.config, ctx.sql_builder, ctx.feature_reporter)
