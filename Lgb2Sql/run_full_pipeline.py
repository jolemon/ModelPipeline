#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执行完整的LightGBM -> Hive SQL Pipeline
支持通过 --model-config 指定模型专属配置文件
"""
import sys
import argparse
from pathlib import Path

# 将src加入路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from pipeline import LgbToSqlPipeline


def main():
    parser = argparse.ArgumentParser(description='LightGBM to Hive SQL Pipeline')
    parser.add_argument(
        '--model-config', '-m',
        type=str,
        default=None,
        help='模型专属配置文件路径，例如 config/models/JDJT_GKB.yaml'
    )
    args = parser.parse_args()

    pipeline = LgbToSqlPipeline(
        config_path='config/config.yaml',
        metadata_path='config/metadata.yaml',
        model_config_path=args.model_config
    )
    
    result = pipeline.run(
        model_path=pipeline.config.model_path,
        sample_config={
            'table_name': pipeline.config.sample_table_name,
            'key': pipeline.config.sample_key,
            'fields': pipeline.config.sample_fields
        },
        output_config={
            'output_table': pipeline.config.output_table_name,
            'output_db': pipeline.config.output_database,
            'coalesce_value': pipeline.config.coalesce_value
        },
        mode=pipeline.config.pipeline_mode,
        save_sql=pipeline.config.pipeline_save_sql,
        generate_score=pipeline.config.pipeline_generate_score,
        score_config={
            'keep_columns': pipeline.config.output_keep_columns
        },
        save_report=pipeline.config.pipeline_save_report
    )
    
    print('\n' + '='*80)
    print('Pipeline执行成功！')
    print(f'入模变量数: {len(result["features"])}')
    print(f'JOIN SQL长度: {len(result["join_sql"])} 字符')
    print(f'打分SQL长度: {len(result["score_sql"]) if result["score_sql"] else 0} 字符')
    print(f'SQL已保存到: {pipeline.config.pipeline_save_sql}')
    print(f'报告已保存到: {pipeline.config.pipeline_save_report}')
    print('='*80)


if __name__ == '__main__':
    main()
