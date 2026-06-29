"""
LightGBM -> Hive SQL 任务流（兼容层）

本文件仅作为兼容入口，实际实现已下沉到 pipeline_pkg/ 包中。

整合模型解析、元数据查询、SQL生成的完整工作流：
1. 打印当前基本配置信息
2. 解析.model文件，获取入模变量
3. 输出这些变量的元数据信息
4. 根据关联逻辑进行表关联，输出子查询语句以及临时表语句

使用示例:
    from pipeline import LgbToSqlPipeline

    pipeline = LgbToSqlPipeline()
    pipeline.run(
        model_path='input/MYJBV4_ZY_lgb_model.model',
        sample_config={
            'table_name': 'dwd_apply_info',
            'key': 'apply_no',
            'fields': ['apply_no', 'cust_no', 'apply_date']
        },
        output_config={
            'output_table': 'model_score_input',
            'output_db': 'my_project',
            'coalesce_value': -999999
        }
    )
"""

import sys
from pathlib import Path

# 将src加入路径
sys.path.insert(0, str(Path(__file__).parent))
# 将根目录加入路径（访问shared/）
sys.path.insert(0, str(Path(__file__).parent.parent))

# 从 pipeline_pkg 统一导入所有公开接口
from src.pipeline_pkg.pipeline_core import LgbToSqlPipeline, PipelineError, run_pipeline
from src.pipeline_pkg.feature_reporter import FeatureReporter
from src.pipeline_pkg.scorer import ScoreGenerator
from src.pipeline_pkg.markdown_reporter import MarkdownReporter

__all__ = [
    'LgbToSqlPipeline',
    'PipelineError',
    'run_pipeline',
    'FeatureReporter',
    'ScoreGenerator',
    'MarkdownReporter',
]


if __name__ == '__main__':
    # 示例用法
    import sys

    if len(sys.argv) < 2:
        model_file = '../input/MYJBV4_ZY_lgb_model.model'
    else:
        model_file = sys.argv[1]

    sql = run_pipeline(
        model_path=model_file,
        sample_table='dwd_apply_info',
        output_table='tmp_model_score_input',
        mode='temp_table',
        save_sql='../output/model_score_input.sql'
    )

    print("\n生成的SQL预览（前500字符）:")
    print(sql[:500])
