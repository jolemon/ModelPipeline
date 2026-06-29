"""
PKL 格式模型加载器

支持从 pickle/joblib 格式的 LightGBM 模型文件加载。
"""

import pickle
import sys
from pathlib import Path
from typing import Optional, Union

from src.model_loaders.base import BaseModelLoader, ModelLoaderError

# 可选依赖
try:
    import lightgbm as lgb
except ImportError:
    lgb = None


class PklModelLoader(BaseModelLoader):
    """PKL格式模型加载器"""

    def load(self, model_path: Optional[Union[str, Path]] = None) -> 'PklModelLoader':
        """
        加载PKL格式模型

        先用pickle加载，失败时尝试joblib（处理numpy版本兼容性问题）。
        加载前会打印当前Python和numpy版本，便于排查环境问题。

        Args:
            model_path: 模型文件路径（可选，若初始化时已提供则可省略）

        Returns:
            PklModelLoader: self，支持链式调用

        Raises:
            ModelLoaderError: 模型路径未提供、文件不存在、lightgbm未安装、
                              或pickle/joblib均加载失败时抛出
        """
        path = Path(model_path) if model_path else self.model_path
        if not path:
            raise ModelLoaderError("未提供模型路径")
        if not path.exists():
            raise ModelLoaderError(f"模型文件不存在: {path}")

        if lgb is None:
            raise ModelLoaderError("未安装lightgbm库，无法加载pkl模型")

        # 打印环境版本信息
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
            err_msg = str(e)
            errors.append(f"pickle.load失败 [ModuleNotFoundError]: {err_msg}")
            if 'numpy' in err_msg:
                errors.append(
                    "  → 原因: 模型文件由更高版本的numpy保存（如numpy 2.x），"
                    "当前环境numpy版本较低（如numpy 1.x），无法识别新模块路径。"
                )
                errors.append(
                    "  → 建议: (1) 升级numpy到与保存模型时一致的版本; "
                    "(2) 或在保存模型的环境中重新导出为 .model 或 .pmml 格式。"
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
                        "  → 原因: 同pickle，模型由更高版本numpy保存，joblib也无法兼容。"
                    )
            except Exception as e:
                errors.append(f"joblib.load失败 [{type(e).__name__}]: {e}")

        if obj is None:
            raise ModelLoaderError(
                f"无法加载pkl模型文件，已尝试以下方式:\n" +
                "\n".join(f"  - {e}" for e in errors) +
                "\n[通用建议] 若版本问题无法解决，请将模型导出为 .model 格式"
                "（LightGBM save_model()），该格式为纯文本，无numpy版本依赖。"
            )

        # 从对象提取特征名
        self.model = obj
        self.model_type = 'pkl'

        if isinstance(obj, lgb.Booster):
            self._feature_names = obj.feature_name()
        elif hasattr(obj, 'booster_'):
            self._feature_names = obj.booster_.feature_name()
        elif hasattr(obj, 'feature_name'):
            self._feature_names = obj.feature_name()
        else:
            raise ModelLoaderError(f"无法从PKL对象提取特征名: {type(obj)}")

        return self
