"""
LightGBM 文本格式模型加载器

解析LightGBM save_model()生成的纯文本文件，无需lightgbm依赖。
"""

import re
from pathlib import Path
from typing import Optional, Union

from src.model_loaders.base import BaseModelLoader, ModelLoaderError


class TextModelLoader(BaseModelLoader):
    """LightGBM文本格式(.model)加载器"""

    def load(self, model_path: Optional[Union[str, Path]] = None) -> 'TextModelLoader':
        """
        加载LightGBM文本格式模型

        解析LightGBM save_model()生成的纯文本文件，从feature_names行提取入模变量列表，
        同时解析模型基本信息（树数量、目标函数、最大特征索引等）。
        无需lightgbm依赖。

        Args:
            model_path: 模型文件路径（可选，若初始化时已提供则可省略）

        Returns:
            TextModelLoader: self，支持链式调用

        Raises:
            ModelLoaderError: 模型路径未提供、文件不存在、或文件中未找到feature_names行时抛出
        """
        path = Path(model_path) if model_path else self.model_path
        if not path:
            raise ModelLoaderError("未提供模型路径")
        if not path.exists():
            raise ModelLoaderError(f"模型文件不存在: {path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise ModelLoaderError(f"读取model文件失败: {str(e)}")

        # 查找 feature_names= 行
        match = re.search(r'^feature_names=([^\n]+)', content, re.MULTILINE)
        if not match:
            raise ModelLoaderError("model文件中未找到feature_names行")

        feature_line = match.group(1).strip()
        if not feature_line:
            raise ModelLoaderError("feature_names行为空")

        # 按空格分割变量名
        fields = [name.strip() for name in feature_line.split(' ') if name.strip()]

        # 同时提取模型基本信息
        info = {'type': 'model', 'path': str(path), 'feature_count': len(fields)}

        tree_match = re.search(r'^num_tree_per_iteration=(\d+)', content, re.MULTILINE)
        if tree_match:
            info['num_tree_per_iteration'] = int(tree_match.group(1))

        obj_match = re.search(r'^objective=([^\n]+)', content, re.MULTILINE)
        if obj_match:
            info['objective'] = obj_match.group(1).strip()

        max_feat_match = re.search(r'^max_feature_idx=(\d+)', content, re.MULTILINE)
        if max_feat_match:
            info['max_feature_idx'] = int(max_feat_match.group(1))

        self.model = info
        self.model_type = 'model'
        self._feature_names = fields

        return self
