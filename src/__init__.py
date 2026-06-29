"""
lgb2sql: LightGBM模型自动转Hive SQL拼接脚本工具

功能：
1. 加载LGB模型，提取入模变量列表
2. 基于变量元数据，自动生成变量拼接SQL
3. 支持变量映射、子查询生成、JOIN关联、后处理、打分映射
"""

__version__ = "1.0.0"
__author__ = "Model Development Team"
