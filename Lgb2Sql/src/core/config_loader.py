"""
配置加载器模块 (Facade)

职责：
1. 加载 config/config.yaml 配置文件
2. 合并模型专属配置覆盖
3. 提供统一的配置访问接口

实现：委托给 6 个子配置类，每个负责一个领域：
- ProjectConfig: 项目信息 + 命名/映射工具
- SQLGenerationConfig: SQL生成参数 + JOIN策略 + 分区控制
- OutputConfig: 输出表配置 + 样本表配置
- PipelineConfig: 流水线执行配置
- OverrideConfig: 覆盖配置 + 别名 + 黑名单
- CreditBridgeConfig: 征信桥接表配置
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.core.config.project_config import ProjectConfig
from src.core.config.sql_generation_config import SQLGenerationConfig
from src.core.config.output_config import OutputConfig
from src.core.config.pipeline_config import PipelineConfig
from src.core.config.override_config import OverrideConfig
from src.core.config.credit_bridge_config import CreditBridgeConfig


class SQLConfig:
    """SQL配置管理器 (Facade)

    所有配置访问通过委托给子配置对象实现，
    外部代码无需修改即可继续使用原有 API。
    """

    _DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"

    def __init__(self, config_path: Optional[str] = None,
                 model_config_path: Optional[str] = None):
        """
        初始化配置

        Args:
            config_path: 基础配置文件路径，默认使用 config/config.yaml
            model_config_path: 模型专属配置文件路径（可选），会覆盖基础配置中的同名参数
        """
        # 1. 加载基础配置
        base_path = Path(config_path) if config_path else self._DEFAULT_CONFIG_PATH
        if not base_path.exists():
            raise FileNotFoundError(f"基础配置文件不存在: {base_path}")

        self._config_path = base_path

        with open(base_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

        # 2. 如果指定了模型配置，合并覆盖
        if model_config_path:
            model_path = Path(model_config_path)
            if model_path.exists():
                with open(model_path, 'r', encoding='utf-8') as f:
                    model_config = yaml.safe_load(f)
                SQLConfig._deep_merge(self._config, model_config)
            else:
                raise FileNotFoundError(f"模型配置文件不存在: {model_path}")

        # 3. 加载外部禁用变量清单文件
        self._load_blacklist_file()

        # 4. 解析配置中的变量引用
        self._resolve_config_vars()

        # 5. 子配置对象（延迟初始化）
        self._project_config: Optional[ProjectConfig] = None
        self._sql_generation_config: Optional[SQLGenerationConfig] = None
        self._output_config: Optional[OutputConfig] = None
        self._pipeline_config: Optional[PipelineConfig] = None
        self._override_config: Optional[OverrideConfig] = None
        self._credit_bridge_config: Optional[CreditBridgeConfig] = None

    def _load_blacklist_file(self):
        """加载外部禁用变量清单文件并合并到配置中"""
        blacklist_file = self._config.get('blacklist_file', '').strip()
        if not blacklist_file:
            return

        base_dir = self._config_path.parent.parent
        file_path = base_dir / blacklist_file

        if not file_path.exists():
            print(f"[WARN] 禁用变量清单文件不存在: {file_path}")
            return

        try:
            file_vars = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        file_vars.append(line)

            if file_vars:
                existing = self._config.get('blacklist_vars', []) or []
                if not isinstance(existing, list):
                    existing = []
                merged = list(dict.fromkeys(existing + file_vars))
                self._config['blacklist_vars'] = merged
                print(f"[禁用变量] 从文件加载 {len(file_vars)} 个，合并后共 {len(merged)} 个")
        except Exception as e:
            print(f"[WARN] 加载禁用变量清单文件失败: {e}")

    def _resolve_config_vars(self):
        """解析配置中的变量引用"""
        vars_map = {
            '${work_no}': self._config.get('project', {}).get('work_no', '${work_no}'),
            '${model_id}': self._config.get('project', {}).get('model_id', '${model_id}'),
            '${model_file_id}': self._config.get('project', {}).get('model_file_id',
                                 self._config.get('project', {}).get('model_id', '${model_file_id}')),
            '${product_code}': self._config.get('project', {}).get('product_code',
                                self._config.get('project', {}).get('platform_alias', '${product_code}')),
        }
        self._config = self._deep_replace_vars(self._config, vars_map)

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """递归合并两个字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                SQLConfig._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    @staticmethod
    def _deep_replace_vars(obj, vars_map):
        """递归替换对象中的变量引用"""
        if isinstance(obj, str):
            result = obj
            for var, value in vars_map.items():
                result = result.replace(var, str(value))
            return result
        elif isinstance(obj, dict):
            return {k: SQLConfig._deep_replace_vars(v, vars_map) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [SQLConfig._deep_replace_vars(item, vars_map) for item in obj]
        return obj

    # ==================== 子配置延迟初始化 ====================

    @property
    def _project(self) -> ProjectConfig:
        if self._project_config is None:
            self._project_config = ProjectConfig(self._config)
        return self._project_config

    @property
    def _sql_generation(self) -> SQLGenerationConfig:
        if self._sql_generation_config is None:
            self._sql_generation_config = SQLGenerationConfig(self._config)
        return self._sql_generation_config

    @property
    def _output(self) -> OutputConfig:
        if self._output_config is None:
            self._output_config = OutputConfig(self._config)
        return self._output_config

    @property
    def _pipeline(self) -> PipelineConfig:
        if self._pipeline_config is None:
            self._pipeline_config = PipelineConfig(self._config)
        return self._pipeline_config

    @property
    def _override(self) -> OverrideConfig:
        if self._override_config is None:
            self._override_config = OverrideConfig(self._config)
        return self._override_config

    @property
    def _credit_bridge(self) -> CreditBridgeConfig:
        if self._credit_bridge_config is None:
            self._credit_bridge_config = CreditBridgeConfig(self._config)
        return self._credit_bridge_config

    # ==================== ProjectConfig 委托 ====================

    @property
    def work_no(self) -> str:
        """工作编号"""
        return self._project.work_no

    @property
    def model_id(self) -> str:
        """模型编号"""
        return self._project.model_id

    @property
    def date_format(self) -> str:
        """日期格式"""
        return self._project.date_format

    @property
    def target_platform(self) -> str:
        """目标平台"""
        return self._project.target_platform

    @property
    def platform_alias(self) -> str:
        """平台别名"""
        return self._project.platform_alias

    @property
    def behavior_platform_priority(self) -> List[str]:
        """行为变量平台优先级列表"""
        return self._project.behavior_platform_priority

    def get_date_str(self, date: Optional[datetime] = None) -> str:
        """生成日期字符串"""
        return self._project.get_date_str(date)

    def resolve_table_name(self, table_name: str) -> str:
        """解析表名，替换 $platform 占位符"""
        return self._project.resolve_table_name(table_name)

    def get_var_type_en(self, category: str) -> str:
        """获取变量类型的英文映射"""
        return self._project.get_var_type_en(category)

    def get_platform_en(self, platform: str) -> str:
        """获取平台的英文映射"""
        return self._project.get_platform_en(platform)

    def get_var_type_short(self, var_type_en: str) -> str:
        """获取变量类型英文简称"""
        return self._project.get_var_type_short(var_type_en)

    def get_alias_prefix(self, var_type_en: str) -> str:
        """获取SQL别名前缀"""
        return self._project.get_alias_prefix(var_type_en)

    def generate_temp_table_name(self, var_type_en: str, seq: int,
                                  date: Optional[datetime] = None) -> str:
        """生成临时表名称"""
        return self._project.generate_temp_table_name(var_type_en, seq, date)

    def generate_group_id(self, platform_en: str, join_key: str) -> str:
        """生成分组标识（英文）"""
        return self._project.generate_group_id(platform_en, join_key)

    # ==================== SQLGenerationConfig 委托 ====================

    @property
    def credit_platforms(self) -> List[str]:
        """征信平台列表"""
        return self._sql_generation.credit_platforms

    @property
    def max_subquery_join(self) -> int:
        """最大子查询关联数"""
        return self._sql_generation.max_subquery_join

    @property
    def subgroup_strategy(self) -> str:
        """子查询分组策略"""
        return self._sql_generation.subgroup_strategy

    @property
    def coalesce_value(self):
        """空值填充值"""
        return self._sql_generation.coalesce_value

    @property
    def partition_field(self) -> str:
        """分区字段"""
        return self._sql_generation.partition_field

    @property
    def partition_var(self) -> str:
        """分区变量名"""
        return self._sql_generation.partition_var

    @property
    def group_merge(self) -> bool:
        """是否启用组内合并"""
        return self._sql_generation.group_merge


    @property
    def naming_style(self) -> str:
        """临时表命名风格"""
        return self._sql_generation.naming_style

    @property
    def join_types(self) -> Dict[str, Dict[str, str]]:
        """JOIN类型配置"""
        return self._sql_generation.join_types

    def get_join_type(self, category: str, platform: str) -> str:
        """获取指定分类/平台的JOIN类型"""
        return self._sql_generation.get_join_type(category, platform)

    @property
    def custom_join_conditions(self) -> Dict[str, Dict[str, Any]]:
        """自定义JOIN条件配置"""
        return self._sql_generation.custom_join_conditions

    def get_custom_join_config(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取单张表的自定义JOIN条件配置"""
        return self._sql_generation.get_custom_join_config(table_name)

    def has_custom_join(self, table_name: str) -> bool:
        """检查表是否配置了自定义JOIN条件"""
        return self._sql_generation.has_custom_join(table_name)

    @property
    def time_range_joins(self) -> Dict[str, Dict[str, Any]]:
        """时间区间匹配配置"""
        return self._sql_generation.time_range_joins

    def get_time_range_config(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取单张表的时间区间匹配配置"""
        return self._sql_generation.get_time_range_config(table_name)

    def is_time_range_table(self, table_name: str) -> bool:
        """检查表是否配置了时间区间匹配"""
        return self._sql_generation.is_time_range_table(table_name)

    @property
    def extra_where_conditions(self) -> Dict[str, Dict[str, List[str]]]:
        """额外WHERE条件配置"""
        return self._sql_generation.extra_where_conditions

    def get_extra_where_conditions(self, category: str, platform: str,
                                    table_name: str) -> List[str]:
        """获取指定表应该应用的额外WHERE条件"""
        return self._sql_generation.get_extra_where_conditions(category, platform, table_name)

    @property
    def partition_control(self) -> Dict[str, Any]:
        """分区控制策略配置"""
        return self._sql_generation.partition_control

    def get_partition_config(self, table_name: str, category: str,
                              platform: str) -> Dict[str, Any]:
        """获取指定表的分区控制配置"""
        return self._sql_generation.get_partition_config(table_name, category, platform)

    # ==================== OutputConfig 委托 ====================

    @property
    def output_table_name(self) -> str:
        """输出表名"""
        return self._output.output_table_name

    @property
    def output_database(self) -> str:
        """输出数据库"""
        return self._output.output_database

    @property
    def output_partition_clause(self) -> str:
        """输出表分区语句"""
        return self._output.output_partition_clause

    @property
    def output_include_sample_fields(self) -> bool:
        """是否在打分表中包含样本表额外字段"""
        return self._output.output_include_sample_fields

    @property
    def output_variable_enabled(self) -> bool:
        """是否在打分表中输出模型变量字段"""
        return self._output.output_variable_enabled

    @property
    def output_variable_sort_by_importance(self) -> bool:
        """变量字段是否按重要度排序"""
        return self._output.output_variable_sort_by_importance

    @property
    def output_variable_top_n(self) -> int:
        """变量字段输出数量限制"""
        return self._output.output_variable_top_n

    @property
    def output_keep_columns(self) -> List[str]:
        """输出表保留列"""
        return self._output.output_keep_columns

    @property
    def sample_table_name(self) -> str:
        """样本表名"""
        return self._output.sample_table_name

    @property
    def sample_key(self) -> str:
        """样本表关联主键"""
        return self._output.sample_key

    @property
    def sample_fields(self) -> List[str]:
        """样本表保留字段列表"""
        return self._output.sample_fields

    # ==================== PipelineConfig 委托 ====================

    @property
    def pipeline_mode(self) -> str:
        """SQL生成模式"""
        return self._pipeline.pipeline_mode

    @property
    def pipeline_save_sql(self) -> str:
        """SQL输出保存路径"""
        return self._pipeline.pipeline_save_sql

    @property
    def pipeline_save_report(self) -> str:
        """Markdown报告保存路径"""
        return self._pipeline.pipeline_save_report

    @property
    def pipeline_generate_score(self) -> bool:
        """是否生成打分SQL"""
        return self._pipeline.pipeline_generate_score

    @property
    def model_path(self) -> str:
        """模型文件路径"""
        return self._pipeline.model_path

    # ==================== OverrideConfig 委托 ====================

    @property
    def variable_overrides(self) -> Dict[str, Dict[str, str]]:
        """变量覆盖配置"""
        return self._override.variable_overrides

    def get_variable_override(self, var_name: str) -> Optional[Dict[str, str]]:
        """获取单个变量的覆盖配置"""
        return self._override.get_variable_override(var_name)

    @property
    def table_join_keys(self) -> Dict[str, Dict[str, str]]:
        """各表关联键覆盖配置"""
        return self._override.table_join_keys

    def get_table_join_config(self, table_name: str) -> Optional[Dict[str, str]]:
        """获取单张表的关联键覆盖配置"""
        return self._override.get_table_join_config(table_name)

    @property
    def variable_aliases(self) -> Dict[str, str]:
        """变量名别名映射配置"""
        return self._override.variable_aliases

    def get_variable_alias(self, var_name: str) -> Optional[str]:
        """获取单个变量的数据库列名别名"""
        return self._override.get_variable_alias(var_name)

    def has_variable_alias(self, var_name: str) -> bool:
        """检查变量是否配置了别名映射"""
        return self._override.has_variable_alias(var_name)

    @property
    def blacklist_vars(self) -> List[str]:
        """禁用变量黑名单"""
        return self._override.blacklist_vars

    def is_blacklisted(self, var_name: str) -> bool:
        """检查变量是否在黑名单中"""
        return self._override.is_blacklisted(var_name)

    def check_blacklist(self, features: List[str]) -> List[str]:
        """检查变量列表中的黑名单命中情况"""
        return self._override.check_blacklist(features)

    # ==================== CreditBridgeConfig 委托 ====================

    @property
    def credit_primary_table(self) -> Dict[str, Any]:
        """征信主键表配置"""
        return self._credit_bridge.credit_primary_table

    @property
    def credit_bridge_enabled(self) -> bool:
        """征信桥接表功能是否启用"""
        return self._credit_bridge.credit_bridge_enabled

    def get_credit_bridge_table_name(self) -> str:
        """获取征信桥接表名称"""
        return self._credit_bridge.get_credit_bridge_table_name(
            self.work_no, self.model_id, self.get_date_str
        )

    def __repr__(self) -> str:
        """返回SQLConfig的字符串表示"""
        return (f"SQLConfig(work_no={self.work_no}, model_id={self.model_id}, "
                f"max_subquery_join={self.max_subquery_join}, "
                f"subgroup_strategy={self.subgroup_strategy})")
