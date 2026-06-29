"""
模型加载器基础模块

提供模型加载异常和基础接口。
"""

from typing import List, Dict, Optional, Union, Any
from pathlib import Path


class ModelLoaderError(Exception):
    """模型加载异常"""
    pass


class BaseModelLoader:
    """模型加载器基类"""

    def __init__(self, model_path: Optional[Union[str, Path]] = None):
        """初始化模型加载器基类

        Args:
            model_path: 模型文件路径（可选）
        """
        self.model_path = Path(model_path) if model_path else None
        self.model: Any = None
        self.model_type: Optional[str] = None
        self._feature_names: List[str] = []

    def load(self, model_path: Optional[Union[str, Path]] = None) -> 'BaseModelLoader':
        """加载模型，子类必须实现

        Args:
            model_path: 模型文件路径（可选，若初始化时已提供则可省略）

        Returns:
            BaseModelLoader: self，支持链式调用

        Raises:
            NotImplementedError: 基类未实现，需由子类覆盖
        """
        raise NotImplementedError

    def get_features(self) -> List[str]:
        """获取特征名列表

        Returns:
            List[str]: 特征名称列表（原始顺序的副本）

        Raises:
            ModelLoaderError: 模型尚未加载时抛出
        """
        if not self._feature_names:
            raise ModelLoaderError("模型尚未加载")
        return self._feature_names.copy()

    def get_feature_count(self) -> int:
        """获取特征数量

        Returns:
            int: 入模特征的总数量

        Raises:
            ModelLoaderError: 模型尚未加载时抛出
        """
        return len(self.get_features())
