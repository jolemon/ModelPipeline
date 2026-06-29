"""
LGB模型入模变量提取器

整合 model_loader.py 和 lgb2sql.py 中的模型加载与变量解析功能，
提供统一的接口从LightGBM模型中提取入模变量列表。

功能：
1. 从文件(.pkl/.pmml)加载模型并提取变量
2. 从已加载的模型对象(Booster/LGBMClassifier)提取变量
3. 获取特征重要性，筛选有效变量(重要性>0)
4. 支持原始变量名和模型dump信息输出

使用示例：
    # 方式1: 从文件提取
    extractor = LgbFeatureExtractor('model.pkl')
    extractor.load_from_file()
    features = extractor.get_all_features()
    valid_features = extractor.get_valid_features()

    # 方式2: 从模型对象提取
    extractor = LgbFeatureExtractor()
    extractor.load_from_object(booster)
    features = extractor.get_all_features()

    # 方式3: 便捷函数
    features = extract_features_from_file('model.pkl')
    valid_features = extract_valid_features_from_file('model.pkl')
"""

import pickle
import warnings
import xml.etree.ElementTree as ET
from typing import List, Optional, Union, Dict, Any
from pathlib import Path

# 可选依赖
try:
    import lightgbm as lgb
except ImportError:
    lgb = None

try:
    import pandas as pd
except ImportError:
    pd = None


class ModelLoaderError(Exception):
    """模型加载异常"""
    pass


class LgbFeatureExtractor:
    """
    LightGBM模型入模变量提取器

    整合 model_loader.py 的文件加载能力和 lgb2sql.py 的模型解析能力，
    提供统一的变量提取接口。
    """

    def __init__(self, model_path: Optional[Union[str, Path]] = None):
        """
        初始化提取器

        Args:
            model_path: 模型文件路径（可选，也可后续通过load_from_file加载）
        """
        self.model_path = Path(model_path) if model_path else None
        self.model: Any = None
        self.model_type: Optional[str] = None
        self._feature_names: List[str] = []
        self._feature_importance: Optional[Dict[str, float]] = None
        self._dump_model: Optional[Dict] = None

    # ==================== 加载方法 ====================

    def load_from_file(self, model_path: Optional[Union[str, Path]] = None) -> 'LgbFeatureExtractor':
        """
        从文件加载模型

        Args:
            model_path: 模型文件路径，若初始化时已提供可省略

        Returns:
            self，支持链式调用
        """
        path = Path(model_path) if model_path else self.model_path
        if not path:
            raise ModelLoaderError("未提供模型路径，请在初始化或load_from_file时指定")
        if not path.exists():
            raise ModelLoaderError(f"模型文件不存在: {path}")

        suffix = path.suffix.lower()
        if suffix == '.pkl':
            return self._load_pkl(path)
        elif suffix == '.pmml':
            return self._load_pmml(path)
        elif suffix == '.model':
            return self._load_model(path)
        else:
            raise ModelLoaderError(f"不支持的模型格式: {suffix}，仅支持 .pkl / .pmml / .model")

    def _load_pkl(self, path: Path) -> 'LgbFeatureExtractor':
        """加载PKL格式模型（整合model_loader.py逻辑）

        先用pickle加载，失败时尝试joblib（处理numpy版本兼容性问题）。
        加载前会打印当前Python和numpy版本，便于排查环境问题。
        """
        if lgb is None:
            raise ModelLoaderError("未安装lightgbm库，无法加载pkl模型")

        # 打印环境版本信息
        import sys
        print(f"[环境信息] Python版本: {sys.version}")
        try:
            import numpy as np
            print(f"[环境信息] NumPy版本: {np.__version__}")
        except ImportError:
            print("[环境信息] NumPy未安装")

        obj = None
        errors = []

        # 方式1: 标准pickle加载
        try:
            with open(path, 'rb') as f:
                obj = pickle.load(f)
        except ModuleNotFoundError as e:
            # 典型的numpy版本不兼容: No module named 'numpy._core'
            err_msg = str(e)
            errors.append(f"pickle.load失败 [ModuleNotFoundError]: {err_msg}")
            if 'numpy' in err_msg:
                errors.append(
                    "  → 原因: 模型文件由更高版本的numpy保存（如numpy 2.x），当前环境numpy版本较低（如numpy 1.x），无法识别新模块路径。"
                )
                errors.append(
                    "  → 建议: (1) 升级numpy到与保存模型时一致的版本; (2) 或在保存模型的环境中重新导出为 .model 或 .pmml 格式。"
                )
        except ImportError as e:
            err_msg = str(e)
            errors.append(f"pickle.load失败 [ImportError]: {err_msg}")
            if 'numpy' in err_msg or 'core' in err_msg:
                errors.append(
                    "  → 原因: numpy版本不兼容，模型依赖的numpy内部模块在当前环境不存在。"
                )
                errors.append(
                    "  → 建议: 使用 .model 格式替代，该格式为纯文本，无numpy版本依赖。"
                )
        except Exception as e:
            errors.append(f"pickle.load失败 [{type(e).__name__}]: {e}")

        # 方式2: joblib加载（处理numpy版本不兼容）
        if obj is None:
            try:
                import joblib
                obj = joblib.load(path)
            except ImportError:
                errors.append("joblib未安装")
            except ModuleNotFoundError as e:
                err_msg = str(e)
                errors.append(f"joblib.load失败 [ModuleNotFoundError]: {err_msg}")
                if 'numpy' in err_msg:
                    errors.append(
                    " → 原因: 同pickle，模型由更高版本numpy保存，joblib也无法兼容。"
                    )
            except Exception as e:
                errors.append(f"joblib.load失败 [{type(e).__name__}]: {e}")

        if obj is None:
            raise ModelLoaderError(
        f"无法加载pkl模型文件，已尝试以下方式:\n" +
        "\n".join(f" - {e}" for e in errors) +
        "\n[通用建议] 若版本问题无法解决，请将模型导出为 .model 格式（LightGBM save_model()），该格式为纯文本，无numpy版本依赖，可直接用于变量提取。"
        )

        # 委托给对象加载方法
        return self.load_from_object(obj)

    def _load_pmml(self, path: Path) -> 'LgbFeatureExtractor':
        """加载PMML格式模型（使用内置XML解析器，无需pypmml依赖）

        注意：
        PMML转换工具（如JPMML-LightGBM）在导出时通常会剔除
        特征重要性为0的变量（即不参与模型分数计算的变量）。
        因此PMML提取的变量数可能少于原始.model或.pkl文件。
        如需获取完整变量列表，建议使用 .model 格式。
        """
        try:
            tree = ET.parse(str(path))
            root = tree.getroot()

            # PMML 4.4 命名空间
            ns = {'pmml': 'http://www.dmg.org/PMML-4_4'}

            # 从DataDictionary提取所有DataField（排除_target）
            dd = root.find('.//pmml:DataDictionary', ns)
            if dd is None:
            # 尝试无命名空间查找
                dd = root.find('.//DataDictionary')

            if dd is None:
                raise ModelLoaderError("PMML文件中未找到DataDictionary节点")

            fields = []
            # 先尝试有命名空间
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


    def _load_model(self, path: Path) -> 'LgbFeatureExtractor':
        """加载LightGBM文本格式模型(.model)（无需lightgbm依赖）

        解析LightGBM save_model()生成的文本文件，
        从feature_names行提取入模变量列表，
        同时解析每棵树的split_feature和split_gain计算特征重要度。
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise ModelLoaderError(f"读取model文件失败: {str(e)}")

        # 查找 feature_names= 行
        import re
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

        # 提取num_tree_per_iteration
        tree_match = re.search(r'^num_tree_per_iteration=(\d+)', content, re.MULTILINE)
        if tree_match:
            info['num_tree_per_iteration'] = int(tree_match.group(1))

        # 提取objective
        obj_match = re.search(r'^objective=([^\n]+)', content, re.MULTILINE)
        if obj_match:
            info['objective'] = obj_match.group(1).strip()

        # 提取max_feature_idx
        max_feat_match = re.search(r'^max_feature_idx=(\d+)', content, re.MULTILINE)
        if max_feat_match:
            info['max_feature_idx'] = int(max_feat_match.group(1))

        # 解析每棵树的 split_feature 和 split_gain，计算特征重要度(gain累加)
        feature_importance = {name: 0.0 for name in fields}
        tree_blocks = re.findall(r'Tree=\d+\n(.+?)(?=\n\nTree=|\Z)', content, re.DOTALL)

        for block in tree_blocks:
            # 提取 split_feature 行
            sf_match = re.search(r'^split_feature=([\d\s]+)', block, re.MULTILINE)
            # 提取 split_gain 行
            sg_match = re.search(r'^split_gain=([\d.eE\-\+\s\.]+)', block, re.MULTILINE)

            if sf_match and sg_match:
                feat_indices = [int(x) for x in sf_match.group(1).strip().split() if x.strip()]
                gains = [float(x) for x in sg_match.group(1).strip().split() if x.strip()]

                for idx, gain in zip(feat_indices, gains):
                    if 0 <= idx < len(fields):
                        feature_importance[fields[idx]] += gain

        self._feature_importance = feature_importance
        self.model = info
        self.model_type = 'model'
        self._feature_names = fields

        return self

    def load_from_object(self, model: Any) -> 'LgbFeatureExtractor':
        """
        从已加载的模型对象提取变量（整合lgb2sql.py逻辑）

        Args:
            model: lightgbm.Booster 或 sklearn API的LGBM模型

        Returns:
            self，支持链式调用
        """
        self.model = model

        if lgb is None:
            raise ModelLoaderError("未安装lightgbm库")

        # 判断模型类型并提取特征名（来自model_loader.py）
        if isinstance(model, lgb.Booster):
            self.model_type = 'booster'
            self._feature_names = model.feature_name()
        elif hasattr(model, 'booster_'):
            # sklearn API: LGBMClassifier / LGBMRegressor
            self.model_type = 'sklearn'
            self._feature_names = model.booster_.feature_name()
        else:
            raise ModelLoaderError(f"无法识别的模型类型: {type(model)}，"
                                   f"期望 lightgbm.Booster 或带 booster_ 属性的sklearn模型")

        return self

    # ==================== 变量提取方法 ====================

    def get_all_features(self) -> List[str]:
        """
        获取所有入模变量名

        Returns:
            变量名列表（原始顺序）
        """
        if not self._feature_names:
            raise ModelLoaderError("模型尚未加载，请先调用load_from_file()或load_from_object()")
        return self._feature_names.copy()

    def get_feature_count(self) -> int:
        """获取入模变量数量

        Returns:
            入模变量总数
        """
        return len(self.get_all_features())

    def get_features(self) -> List[str]:
        """获取所有入模变量名（ModelVarDiff 兼容别名）

        Returns:
            变量名列表（原始顺序）
        """
        return self.get_all_features()

    def get_feature_importance(self, importance_type: str = 'gain') -> Dict[str, float]:
        """
        获取特征重要性（整合lgb2sql.py逻辑）

        对于 .model 文本格式，已在加载时通过解析 split_gain 计算好重要性，
        直接返回即可（importance_type 参数被忽略）。

        Args:
            importance_type: 重要性类型，可选 'split', 'gain'（默认）

        Returns:
            {变量名: 重要性值} 字典
        """
        if self._feature_importance is not None:
            return self._feature_importance.copy()

        if not self.model:
            raise ModelLoaderError("模型尚未加载")

        if self.model_type == 'pmml':
            raise ModelLoaderError("PMML模型不支持特征重要性计算")

        if self.model_type == 'model':
            raise ModelLoaderError(".model 格式应在加载时已计算重要性，请检查加载逻辑")

        if self.model_type == 'booster':
            booster = self.model
        elif self.model_type == 'sklearn':
            booster = self.model.booster_
        else:
            raise ModelLoaderError(f"不支持的模型类型: {self.model_type}")

        try:
            importances = booster.feature_importance(importance_type=importance_type)
            self._feature_importance = dict(zip(self._feature_names, importances))
        except Exception as e:
            raise ModelLoaderError(f"计算特征重要性失败: {str(e)}")

        return self._feature_importance.copy()

    def get_valid_features(self, importance_type: str = 'gain') -> List[str]:
        """
        获取有效变量（重要性 > 0）

        整合lgb2sql.py中transform_v2筛选有效特征的逻辑，
        重要性为0的变量在模型预测中不会被使用，可以剔除。

        Args:
            importance_type: 重要性类型，默认'gain'

        Returns:
            有效变量名列表
        """
        importance = self.get_feature_importance(importance_type)
        return [name for name, imp in importance.items() if imp > 0]

    def get_valid_feature_count(self, importance_type: str = 'gain') -> int:
        """获取有效变量数量（重要性 > 0）

        Args:
            importance_type: 重要性类型，默认'gain'

        Returns:
            有效变量数量
        """
        return len(self.get_valid_features(importance_type))

    def get_model_dump(self) -> Dict:
        """
        获取模型dump信息（整合lgb2sql.py的get_dump_model）

        Returns:
            模型dump后的字典，包含tree_info等
        """
        if self._dump_model is not None:
            return self._dump_model

        if not self.model:
            raise ModelLoaderError("模型尚未加载")

        if self.model_type == 'pmml':
            raise ModelLoaderError("PMML模型不支持dump")

        # 来自lgb2sql.py的get_dump_model逻辑
        if self.model_type == 'sklearn' and hasattr(self.model, '_Booster'):
            lgb_model = self.model._Booster
        else:
            lgb_model = self.model

        try:
            self._dump_model = lgb_model.dump_model()
        except Exception as e:
            raise ModelLoaderError(f"模型dump失败: {str(e)}")

        return self._dump_model

    def get_tree_count(self) -> int:
        """获取树的数量

        Returns:
            模型中的树数量
        """
        dump = self.get_model_dump()
        return len(dump.get('tree_info', []))

    # ==================== 信息汇总 ====================

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息摘要

        Returns:
            包含模型路径、类型、变量数、变量名等信息的字典
        """
        info = {
            'model_path': str(self.model_path) if self.model_path else None,
            'model_type': self.model_type,
            'feature_count': self.get_feature_count(),
            'feature_names': self.get_all_features(),
        }

        # 若支持，添加树数量和有效变量数
        try:
            info['tree_count'] = self.get_tree_count()
            info['valid_feature_count'] = self.get_valid_feature_count()
        except ModelLoaderError:
            pass  # PMML模型不支持

        return info

    def print_summary(self) -> None:
        """打印模型变量摘要到控制台"""
        info = self.get_model_info()
        print("=" * 60)
        print("LGB模型变量摘要")
        print("=" * 60)
        print(f"模型路径: {info.get('model_path', 'N/A')}")
        print(f"模型类型: {info.get('model_type', 'N/A')}")
        print(f"总变量数: {info.get('feature_count', 0)}")
        if 'valid_feature_count' in info:
            print(f"有效变量数: {info['valid_feature_count']}")
        if 'tree_count' in info:
            print(f"树数量: {info['tree_count']}")
        print("-" * 60)
        for i, name in enumerate(info.get('feature_names', []), 1):
            print(f"  {i:3d}. {name}")
        print("=" * 60)


# ==================== 便捷函数 ====================

def extract_features_from_file(model_path: Union[str, Path]) -> List[str]:
    """
    便捷函数：从模型文件提取所有变量名

    Args:
        model_path: 模型文件路径(.pkl/.pmml)

    Returns:
        变量名列表
    """
    extractor = LgbFeatureExtractor(model_path)
    extractor.load_from_file()
    return extractor.get_all_features()


def extract_valid_features_from_file(
    model_path: Union[str, Path],
    importance_type: str = 'gain'
) -> List[str]:
    """
    便捷函数：从模型文件提取有效变量名（重要性 > 0）

    Args:
        model_path: 模型文件路径(.pkl/.pmml)
        importance_type: 重要性类型，默认'gain'

    Returns:
        有效变量名列表
    """
    extractor = LgbFeatureExtractor(model_path)
    extractor.load_from_file()
    return extractor.get_valid_features(importance_type)


def extract_features_from_object(model: Any) -> List[str]:
    """
    便捷函数：从模型对象提取所有变量名

    Args:
        model: lightgbm.Booster 或 sklearn LGBM模型

    Returns:
        变量名列表
    """
    extractor = LgbFeatureExtractor()
    extractor.load_from_object(model)
    return extractor.get_all_features()


def load_model(model_path: Union[str, Path]) -> 'LgbFeatureExtractor':
    """
    根据文件后缀自动选择加载器并加载（ModelVarDiff 兼容接口）

    Args:
        model_path: 模型文件路径(.pkl/.pmml/.model)

    Returns:
        加载完成的 LgbFeatureExtractor，可直接调用 get_features() / get_all_features()
    """
    extractor = LgbFeatureExtractor(model_path)
    extractor.load_from_file()
    return extractor
