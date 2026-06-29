"""
PMML 格式模型加载器

使用内置XML解析器从PMML文件提取特征名，无需pypmml依赖。
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Union

from model_loaders.base import BaseModelLoader, ModelLoaderError


class PmmlModelLoader(BaseModelLoader):
    """PMML格式模型加载器"""

    def load(self, model_path: Optional[Union[str, Path]] = None) -> 'PmmlModelLoader':
        """
        加载PMML格式模型

        使用内置XML解析器从PMML文件提取特征名，无需pypmml依赖。

        注意：
        PMML转换工具在导出时通常会剔除特征重要性为0的变量，
        因此PMML提取的变量数可能少于原始.model或.pkl文件。

        Args:
        model_path: 模型文件路径（可选，若初始化时已提供则可省略）

        Returns:
        PmmlModelLoader: self，支持链式调用

        Raises:
        ModelLoaderError: 模型路径未提供、文件不存在、或XML解析失败时抛出
        """
        path = Path(model_path) if model_path else self.model_path
        if not path:
            raise ModelLoaderError("未提供模型路径")
        if not path.exists():
            raise ModelLoaderError(f"模型文件不存在: {path}")

        try:
            tree = ET.parse(str(path))
            root = tree.getroot()

            # PMML 4.4 命名空间
            ns = {'pmml': 'http://www.dmg.org/PMML-4_4&'}

            # 从DataDictionary提取所有DataField（排除_target）
            dd = root.find('.//pmml:DataDictionary', ns)
            if dd is None:
                dd = root.find('.//DataDictionary')

            if dd is None:
                raise ModelLoaderError("PMML文件中未找到DataDictionary节点")

            fields = []
            data_fields = dd.findall('pmml:DataField', ns)
            if not data_fields:
                data_fields = dd.findall('DataField')

            for df in data_fields:
                name = df.get('name')
            if name and name != '_target':
                fields.append(name)

            self.model = {'type': 'pmml', 'path': str(path), 'feature_count': len(fields)}
            self.model_type = 'pmml'
            self._feature_names = fields

        except ET.ParseError as e:
            raise ModelLoaderError(f"PMML文件XML解析失败: {str(e)}")
        except Exception as e:
            raise ModelLoaderError(f"加载pmml模型失败: {str(e)}")

        return self

