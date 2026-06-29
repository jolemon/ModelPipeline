"""
共享风控建模参考库

提供评分卡建模的标准实现，包含分箱、WOE/IV/KS、逐步回归、评分卡生成等。
原位于 ModelReport/model_library/，迁移至 shared/ 供全仓引用。

核心类:
    Binner      — 变量分箱引擎 (scorecard_jsb.py)
    Scorecard   — 评分卡建模引擎 (scorecard_jsb.py)

工具函数 (dataset_learn.py):
    calc_missing, calc_psi, calc_iv, calculate_ks, fillna_strategy

配置:
    feature_warehouse_path (config.py)

注意:
    - scorecard_jsb.py 依赖外部包 tubao（当前未提供）
    - model_learn.py 依赖 optuna/sklearn2pmml/datasources 等建模平台包
    - examples/计算iv_ks例子.py 为参考脚本，不可直接运行
"""
