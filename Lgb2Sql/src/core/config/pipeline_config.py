"""
Pipeline配置模块

职责：流水线执行配置 + 模型路径
"""

from typing import Dict, Any


class PipelineConfig:
    """Pipeline配置：SQL生成模式、保存路径、模型路径"""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    @property
    def pipeline_mode(self) -> str:
        """SQL生成模式：cte 或 temp_table"""
        return self._config.get('pipeline', {}).get('mode', 'temp_table')

    @property
    def pipeline_save_sql(self) -> str:
        """SQL输出保存路径"""
        return self._config.get('pipeline', {}).get('save_sql', '')

    @property
    def pipeline_save_report(self) -> str:
        """Markdown报告保存路径"""
        return self._config.get('pipeline', {}).get('save_report', '')

    @property
    def pipeline_generate_score(self) -> bool:
        """是否生成打分SQL"""
        return self._config.get('pipeline', {}).get('generate_score', True)

    @property
    def model_path(self) -> str:
        """模型文件路径"""
        return self._config.get('model', {}).get('path', '')
