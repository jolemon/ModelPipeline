"""
共享模型加载器

提供从 LightGBM 模型文件(.pkl/.pmml/.model)提取入模变量的统一接口。
基于 Lgb2Sql 的 LgbFeatureExtractor 实现。

使用示例:
    from shared.model_loaders import load_model, LgbFeatureExtractor

    # 方式1: 工厂函数（ModelVarDiff 风格）
    loader = load_model('model.pkl')
    features = loader.get_features()

    # 方式2: 直接使用提取器（Lgb2Sql 风格）
    extractor = LgbFeatureExtractor('model.pkl')
    extractor.load_from_file()
    features = extractor.get_all_features()
    importance = extractor.get_feature_importance()
"""

from shared.model_loaders.extractor import (
    LgbFeatureExtractor,
    ModelLoaderError,
    load_model,
    extract_features_from_file,
    extract_valid_features_from_file,
    extract_features_from_object,
)

__all__ = [
    'LgbFeatureExtractor',
    'ModelLoaderError',
    'load_model',
    'extract_features_from_file',
    'extract_valid_features_from_file',
    'extract_features_from_object',
]
