"""
特征提取 Stage

职责：解析模型文件，提取入模变量，过滤零重要度特征
"""

from pathlib import Path
from typing import List, Optional

from src.core.lgb_feature_extractor import LgbFeatureExtractor


class FeatureExtractionStage:
    """特征提取 Stage：解析模型，提取变量"""

    def execute(self, ctx, model_path: str,
                filter_zero_importance: bool = True) -> List[str]:
        """解析模型文件，获取入模变量

        Args:
            ctx: PipelineContext
            model_path: 模型文件路径
            filter_zero_importance: 是否过滤重要度为0的特征

        Returns:
            入模变量名列表
        """
        print("\n" + "=" * 70)
        print(" 步骤2: 解析模型文件，获取入模变量 ")
        print("=" * 70)

        path = Path(model_path)
        print(f"\n模型文件: {path}")
        print(f"文件格式: {path.suffix}")

        extractor = LgbFeatureExtractor(model_path)
        extractor.load_from_file()

        all_features = extractor.get_all_features()
        ctx.zero_importance_features = []

        # 计算特征重要度并过滤为0的特征
        if filter_zero_importance and extractor.model_type != 'pmml':
            try:
                importance = extractor.get_feature_importance()
                valid_features = [name for name in all_features if importance.get(name, 0) > 0]
                ctx.zero_importance_features = [
                    name for name in all_features if importance.get(name, 0) == 0
                ]

                if ctx.zero_importance_features:
                    print(f"\n[INFO] 特征重要度分析完成")
                    print(f"  总变量数: {len(all_features)}")
                    print(f"  有效变量数(重要度>0): {len(valid_features)}")
                    print(f"  零重要度变量数(已过滤): {len(ctx.zero_importance_features)}")
                    print(f"\n[NOTE] 以下 {len(ctx.zero_importance_features)} 个变量重要度为0，不参与模型计算，已自动过滤:")
                    for i, name in enumerate(ctx.zero_importance_features, 1):
                        print(f"  {i:3d}. {name} (gain=0.000)")
                else:
                    print(f"\n[INFO] 特征重要度分析完成，所有 {len(all_features)} 个变量均参与模型计算")

                ctx.features = valid_features
            except Exception as e:
                print(f"\n[WARN] 特征重要度计算失败({e})，使用全部 {len(all_features)} 个变量")
                ctx.features = all_features
        else:
            ctx.features = all_features

        # 记录模型信息
        ctx.model_info = {
            'model_type': extractor.model_type,
        }
        if hasattr(extractor, 'model') and isinstance(extractor.model, dict):
            if 'objective' in extractor.model:
                ctx.model_info['objective'] = extractor.model['objective']
            if 'num_tree_per_iteration' in extractor.model:
                ctx.model_info['num_trees'] = extractor.model['num_tree_per_iteration']

        print(f"\n/:em_209:/ 成功提取入模变量: {len(ctx.features)} 个")
        print(f"  模型类型: {extractor.model_type}")
        if 'objective' in ctx.model_info:
            print(f"  目标函数: {ctx.model_info['objective']}")
        if 'num_trees' in ctx.model_info:
            print(f"  树数量:   {ctx.model_info['num_trees']}")

        print(f"\n变量列表（前20个）:")
        for i, name in enumerate(ctx.features[:20], 1):
            print(f"  {i:3d}. {name}")
        if len(ctx.features) > 20:
            print(f"  ... 共 {len(ctx.features)} 个变量")

        return ctx.features
