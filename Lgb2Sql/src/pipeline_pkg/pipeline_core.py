"""
任务流编排模块 (Facade)

整合模型解析、元数据查询、SQL生成的完整工作流。
实现委托给各 Stage 类，LgbToSqlPipeline 仅负责编排。
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

from src.pipeline_pkg.stages.context import PipelineContext
from src.pipeline_pkg.stages.config_stage import ConfigStage
from src.pipeline_pkg.stages.feature_stage import FeatureExtractionStage
from src.pipeline_pkg.stages.metadata_stage import MetadataReportStage
from src.pipeline_pkg.stages.sql_stage import SQLGenerationStage
from src.pipeline_pkg.stages.score_stage import ScoreGenerationStage


class PipelineError(Exception):
    """任务流异常"""
    pass


class LgbToSqlPipeline:
    """LightGBM模型 -> Hive SQL 生成任务流 (Facade)

    自动完成从模型文件到可执行SQL的完整转换流程。
    所有具体实现委托给 Stage 类。
    """

    def __init__(self,
                 config_path: Optional[str] = None,
                 metadata_path: Optional[str] = None,
                 model_config_path: Optional[str] = None):
        """
        初始化任务流

        Args:
            config_path: 配置文件路径
            metadata_path: 元数据文件路径
            model_config_path: 模型专属配置文件路径（可选）
        """
        self._ctx = PipelineContext()

        # 初始化所有组件（ConfigStage 负责加载配置、元数据、应用覆盖、初始化下游组件）
        ConfigStage().execute(self._ctx, config_path, metadata_path, model_config_path)

        # 初始化各 Stage
        self._feature_stage = FeatureExtractionStage()
        self._metadata_stage = MetadataReportStage()
        self._sql_stage = SQLGenerationStage()
        self._score_stage = ScoreGenerationStage()

    # ========== 属性委托给 Context ==========

    @property
    def config(self):
        """SQL配置"""
        return self._ctx.config

    @property
    def metadata(self):
        """元数据管理器"""
        return self._ctx.metadata

    @property
    def sql_builder(self):
        """SQL构建器"""
        return self._ctx.sql_builder

    @property
    def feature_reporter(self):
        """特征报告器"""
        return self._ctx.feature_reporter

    @property
    def score_generator(self):
        """打分SQL生成器"""
        return self._ctx.score_generator

    @property
    def markdown_reporter(self):
        """Markdown报告生成器"""
        return self._ctx.markdown_reporter

    # ========== 内部辅助方法 ==========

    def _ensure_features_loaded(self, features: Optional[List[str]] = None) -> List[str]:
        """确保特征已加载"""
        features = features or self._ctx.features
        if not features:
            raise PipelineError("尚未提取入模变量，请先调用extract_features()")
        return features

    def _get_variable_issues(self) -> Dict[str, Any]:
        """获取当前变量的异常问题汇总"""
        issues = {'missing': [], 'ambiguous': {}}

        if self._ctx.feature_meta:
            issues['missing'] = [
                v for v, m in self._ctx.feature_meta.items()
                if m.get('status') == 'NOT_FOUND'
            ]

        if self._ctx.features:
            issues['ambiguous'] = self.metadata.find_ambiguous_variables(self._ctx.features)

        return issues

    # ========== 步骤1: 打印配置 ==========

    def print_config(self) -> None:
        """打印当前基本配置信息"""
        print("=" * 70)
        print(" 任务流配置信息 ")
        print("=" * 70)

        print("\n[项目配置]")
        print(f"  工作编号 (work_no):     {self.config.work_no}")
        print(f"  模型编号 (model_id):    {self.config.model_id}")
        print(f"  日期格式:               {self.config.date_format}")
        print(f"  当前日期:               {self.config.get_date_str()}")

        print("\n[SQL生成参数]")
        print(f"  最大子查询关联数:       {self.config.max_subquery_join}")
        print(f"  空值填充值 (COALESCE):  {self.config.coalesce_value}")
        print(f"  分区字段:               {self.config.partition_field}")
        print(f"  分区变量:               {self.config.partition_var}")

        print("\n[元数据概览]")
        print(f"  变量总数:               {len(self.metadata.variables)}")
        print(f"  表总数:                 {len(self.metadata.tables)}")

        platform_stats: Dict[str, int] = {}
        for tbl in self.metadata.tables.values():
            platform = tbl.platform or 'unknown'
            platform_stats[platform] = platform_stats.get(platform, 0) + 1

        print("\n[平台分布]")
        for platform, count in sorted(platform_stats.items()):
            print(f"  {platform:20s}: {count:3d} 张表")

        blacklist = self.config.blacklist_vars
        if blacklist:
            print(f"\n[禁用变量黑名单]")
            print(f"  共 {len(blacklist)} 个变量")
            for var in blacklist[:5]:
                print(f"    - {var}")
            if len(blacklist) > 5:
                print(f"    ... 等 {len(blacklist)} 个变量")

        print("=" * 70)

    # ========== 步骤2: 解析模型 ==========

    def extract_features(self, model_path: str,
                         filter_zero_importance: bool = True) -> List[str]:
        """解析模型文件，获取入模变量"""
        return self._feature_stage.execute(self._ctx, model_path, filter_zero_importance)

    # ========== 步骤3: 输出元数据 ==========

    def print_metadata(self, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """输出入模变量的元数据信息"""
        return self._metadata_stage.execute(self._ctx, features)

    # ========== 步骤4: 生成SQL ==========

    def generate_sql(self,
                     features: Optional[List[str]] = None,
                     sample_config: Optional[dict] = None,
                     output_config: Optional[dict] = None,
                     mode: str = 'temp_table') -> str:
        """根据关联逻辑进行表关联，输出SQL语句"""
        return self._sql_stage.execute(self._ctx, features, sample_config, output_config, mode)

    # ========== 步骤5: 生成打分SQL ==========

    def generate_score_sql(self,
                           model_path: str,
                           keep_columns: Optional[List[str]] = None,
                           input_table: Optional[str] = None,
                           work_no: Optional[str] = None,
                           model_id: Optional[str] = None,
                           table_date: Optional[str] = None,
                           scorecard_shift: float = 533.903595,
                           scorecard_slope: float = 72.134752,
                           scorecard_round: int = 2,
                           round_decimal: int = 32,
                           verbose: bool = True) -> str:
        """生成模型打分SQL"""
        return self._score_stage.execute(
            self._ctx, model_path, keep_columns, input_table,
            work_no, model_id, table_date,
            scorecard_shift, scorecard_slope, scorecard_round,
            round_decimal, verbose
        )

    # ========== 完整执行流 ==========

    def run(self,
            model_path: str,
            sample_config: Optional[dict] = None,
            output_config: Optional[dict] = None,
            mode: str = 'temp_table',
            save_sql: Optional[str] = None,
            generate_score: bool = True,
            score_config: Optional[dict] = None,
            save_report: Optional[str] = None,
            verbose: bool = True) -> Dict[str, Any]:
        """执行完整任务流（配置打印 -> 特征提取 -> 元数据报告 -> SQL生成 -> 打分SQL）"""
        if verbose:
            print("\n" + "=" * 80)
            print(" LightGBM -> Hive SQL 任务流启动 ")
            print(f" 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 80)

        self.print_config()
        self.extract_features(model_path)
        self.print_metadata()

        join_sql = self.generate_sql(
            features=self._ctx.features,
            sample_config=sample_config,
            output_config=output_config,
            mode=mode
        )

        result = {
            'join_sql': join_sql,
            'score_sql': None,
            'features': self._ctx.features.copy(),
            'feature_metadata': self._ctx.feature_meta.copy(),
            'zero_importance_features': getattr(self._ctx, 'zero_importance_features', [])
        }

        if generate_score:
            score_cfg = score_config or {}
            if 'input_table' not in score_cfg and output_config:
                score_cfg['input_table'] = output_config.get('output_table')

            score_sql = self.generate_score_sql(
                model_path=model_path,
                keep_columns=score_cfg.get('keep_columns', ['apply_no']),
                input_table=score_cfg.get('input_table'),
                work_no=score_cfg.get('work_no'),
                model_id=score_cfg.get('model_id'),
                table_date=score_cfg.get('table_date'),
                scorecard_shift=score_cfg.get('scorecard_shift', 533.903595),
                scorecard_slope=score_cfg.get('scorecard_slope', 72.134752),
                scorecard_round=score_cfg.get('scorecard_round', 2),
                round_decimal=score_cfg.get('round_decimal', 32),
                verbose=verbose
            )
            result['score_sql'] = score_sql

        # 保存 SQL（可选）
        if save_sql:
            save_path = Path(save_sql)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write("-- ===== 步骤4: JOIN SQL =====\n")
                f.write(result['join_sql'])
                f.write("\n\n")
                if result['score_sql']:
                    f.write("-- ===== 步骤5: 打分SQL =====\n")
                    f.write(result['score_sql'])
            if verbose:
                print(f"\n/:em_209:/ SQL已保存到: {save_path}")
                
        # 保存 Markdown 报告（可选）
        if save_report:
            md_content = self.markdown_reporter.generate(
                model_path=model_path,
                result=result,
                sample_config=sample_config,
                output_config=output_config,
                mode=mode,
                generate_score=generate_score
            )
            report_path = Path(save_report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            if verbose:
                print(f"\n/:em_209:/ 报告已保存到: {report_path}")

        # 警告汇总
        issues = self._get_variable_issues()
        warnings = []

        if issues['missing']:
            warnings.append(f"未命中元数据变量: {len(issues['missing'])} 个")
        if issues['ambiguous']:
            warnings.append(f"歧义变量（多表匹配）: {len(issues['ambiguous'])} 个")

        blacklisted = self.config.check_blacklist(self._ctx.features)
        if blacklisted:
            warnings.append(f"黑名单禁用变量: {len(blacklisted)} 个")

        if warnings and verbose:
            print("\n[WARN] 警告汇总")
            for w in warnings:
                print(f"  ! {w}")

        if verbose:
            print("\n" + "=" * 80)
            print(" 任务流执行完成 ")
            print("=" * 80)

        return result

    def get_features(self) -> List[str]:
        """获取当前已提取的入模变量列表"""
        return self._ctx.features.copy()

    def get_feature_metadata(self) -> Dict[str, Any]:
        """获取当前已查询的变量元数据"""
        return self._ctx.feature_meta.copy()

    # ========== 元数据统计入口 ==========

    def print_metadata_statistics(self) -> Dict[str, Any]:
        """输出当前元数据的统计信息"""
        stats = self.metadata.get_statistics()
        self.metadata.print_statistics()
        return stats

    def get_metadata_statistics(self) -> Dict[str, Any]:
        """获取当前元数据的统计信息（不打印）"""
        return self.metadata.get_statistics()


# ==================== 便捷函数 ====================

def run_pipeline(model_path: str,
                 sample_table: str = 'dwd_apply_info',
                 output_table: str = 'model_score_input',
                 mode: str = 'temp_table',
                 save_sql: Optional[str] = None) -> Dict[str, Any]:
    """便捷函数：一键执行完整任务流"""
    pipeline = LgbToSqlPipeline()

    sample_config = {
        'table_name': sample_table,
        'key': 'apply_no',
        'fields': ['apply_no']
    }

    output_config = {
        'output_table': output_table,
        'output_db': '',
        'coalesce_value': -999999
    }

    return pipeline.run(
        model_path=model_path,
        sample_config=sample_config,
        output_config=output_config,
        mode=mode,
        save_sql=save_sql
    )
