"""
模型加载器包

提供从多种格式加载 LightGBM 模型的统一接口。
"""

from typing import Union
from pathlib import Path

from model_loaders.base import BaseModelLoader, ModelLoaderError
from model_loaders.pkl_loader import PklModelLoader
from model_loaders.pmml_loader import PmmlModelLoader
from model_loaders.text_loader import TextModelLoader


def load_model(model_path: Union[str, Path]) -> BaseModelLoader:
    """
    根据文件后缀自动选择加载器

    Args:
        model_path: 模型文件路径

    Returns:
        加载完成的模型加载器
    """
    path = Path(model_path)
    suffix = path.suffix.lower()

    if suffix == '.pkl':
        loader = PklModelLoader(path)
    elif suffix == '.pmml':
        loader = PmmlModelLoader(path)
    elif suffix == '.model':
        loader = TextModelLoader(path)
    else:
        raise ModelLoaderError(f"不支持的模型格式: {suffix}，仅支持 .pkl / .pmml / .model")

    loader.load()
    return loader


__all__ = [
    'BaseModelLoader',
    'ModelLoaderError',
    'PklModelLoader',
    'PmmlModelLoader',
    'TextModelLoader',
    'load_model'
]
