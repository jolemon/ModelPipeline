"""
变量元数据管理模块（P4 重构后）

职责：
1. 加载和解析变量元数据（YAML/JSON格式，支持pickle缓存）
2. 变量/表的基础查询（get_variable, get_table, group_variables_by_*）

其他职责已拆分至独立模块：
- 变量分类分析  -> src.metadata.variable_classifier.VariableClassifier
- 配置覆盖应用  -> src.metadata.override_applier.OverrideApplier
- 统计报告输出  -> src.metadata.metadata_statistics.MetadataStatistics
"""

import yaml
import json
import pickle
import os
from pathlib import Path
from typing import List, Dict, Optional, Union, Any
from collections import defaultdict

from src.metadata.models import VariableMetadata, TableMetadata


class MetadataManager:
    """
    变量元数据管理器

    负责元数据的加载、解析和基础查询。
    分析/覆盖/统计功能通过代理属性访问独立模块。
    """

    def __init__(self, metadata_path: Optional[Union[str, Path]] = None):
        """
        初始化元数据管理器

        Args:
            metadata_path: 元数据文件路径（YAML/JSON）
        """
        self.metadata_path = Path(metadata_path) if metadata_path else None
        self.variables: Dict[str, VariableMetadata] = {}
        self.tables: Dict[str, TableMetadata] = {}
        self._loaded = False

        # 延迟初始化的代理对象
        self._classifier = None
        self._override_applier = None
        self._statistics = None

    # ==================== 加载与解析 ====================

    def load(self, metadata_path: Optional[Union[str, Path]] = None) -> 'MetadataManager':
        """加载元数据文件（支持自动pickle缓存加速）

        Args:
            metadata_path: 元数据文件路径，如未提供则使用初始化时的路径

        Returns:
            self，支持链式调用
        """
        path = Path(metadata_path) if metadata_path else self.metadata_path
        if not path or not path.exists():
            raise FileNotFoundError(f"元数据文件不存在: {path}")

        # 尝试加载pickle缓存
        cache_path = path.with_suffix('.pkl')
        use_cache = False
        if cache_path.exists():
            try:
                src_mtime = os.path.getmtime(path)
                cache_mtime = os.path.getmtime(cache_path)
                if cache_mtime >= src_mtime:
                    with open(cache_path, 'rb') as f:
                        data = pickle.load(f)
                    use_cache = True
            except Exception:
                use_cache = False

        if not use_cache:
            suffix = path.suffix.lower()
            with open(path, 'r', encoding='utf-8') as f:
                if suffix in ('.yaml', '.yml'):
                    data = yaml.safe_load(f)
                elif suffix == '.json':
                    data = json.load(f)
                else:
                    raise ValueError(f"不支持的元数据格式: {suffix}")

            # 保存pickle缓存（失败不影响主流程）
            try:
                with open(cache_path, 'wb') as f:
                    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            except Exception:
                pass

        self._parse_metadata(data)
        self._loaded = True
        return self

    def _parse_metadata(self, data: dict) -> None:
        """解析元数据

        支持完整格式（同时包含variables和tables）
        """
        self.variables.clear()
        self.tables.clear()

        # 解析变量列表
        if 'variables' in data:
            for var_data in data['variables']:
                valid_keys = {f.name for f in VariableMetadata.__dataclass_fields__.values()}
                filtered_data = {k: v for k, v in var_data.items() if k in valid_keys}
                var = VariableMetadata(**filtered_data)
                self.variables[var.var_name] = var

        # 解析表分组
        if 'tables' in data:
            for tbl_data in data['tables']:
                table_name = tbl_data['table_name']
                var_list = tbl_data.get('variables', [])

                valid_keys = {f.name for f in TableMetadata.__dataclass_fields__.values()}
                filtered_data = {
                    k: v for k, v in tbl_data.items()
                    if k in valid_keys and k not in ('variables', 'table_name')
                }

                table_meta = TableMetadata(table_name=table_name, **filtered_data)
                table_meta.variables = var_list
                self.tables[table_name] = table_meta

                # 补充变量索引中缺失的信息
                for var_name in var_list:
                    if var_name in self.variables:
                        var = self.variables[var_name]
                        if not var.source_table:
                            var.source_table = table_name
                        if not var.category:
                            var.category = table_meta.category
                        if not var.platform:
                            var.platform = table_meta.platform
                        if not var.partition_field:
                            var.partition_field = table_meta.partition_field
                        if not var.join_key:
                            var.join_key = table_meta.join_key
                        if not var.join_key_candidates and table_meta.join_key_candidates:
                            var.join_key_candidates = table_meta.join_key_candidates
                    else:
                        var = VariableMetadata(
                            var_name=var_name,
                            source_table=table_name,
                            category=table_meta.category,
                            platform=table_meta.platform,
                            partition_field=table_meta.partition_field,
                            join_key=table_meta.join_key,
                            join_key_candidates=table_meta.join_key_candidates
                        )
                        self.variables[var_name] = var

        if not self.variables and not self.tables:
            raise ValueError("元数据格式错误：需要包含 'variables' 或 'tables' 键")

    # ==================== 基础查询 ====================

    def get_variable(self, var_name: str) -> Optional[VariableMetadata]:
        """查询单个变量的元数据"""
        return self.variables.get(var_name)

    def get_table(self, table_name: str) -> Optional[TableMetadata]:
        """查询单张表的元数据"""
        return self.tables.get(table_name)

    def get_table_variables(self, table_name: str) -> List[str]:
        """获取某张表下的所有变量"""
        table = self.tables.get(table_name)
        return table.variables if table else []

    def group_variables_by_table(self, var_names: List[str]) -> Dict[str, List[str]]:
        """将变量列表按来源表分组"""
        groups = defaultdict(list)
        for var_name in var_names:
            var_meta = self.get_variable(var_name)
            if var_meta and var_meta.source_table:
                groups[var_meta.source_table].append(var_name)
            else:
                groups['_UNKNOWN_'].append(var_name)
        return dict(groups)

    def group_variables_by_category(self, var_names: List[str]) -> Dict[str, List[str]]:
        """将变量列表按分类分组"""
        groups = defaultdict(list)
        for var_name in var_names:
            var_meta = self.get_variable(var_name)
            category = var_meta.category if var_meta else '_UNKNOWN_'
            groups[category].append(var_name)
        return dict(groups)

    def group_variables_by_platform(self, var_names: List[str]) -> Dict[str, List[str]]:
        """将变量列表按平台（二级分类）分组"""
        groups = defaultdict(list)
        for var_name in var_names:
            var_meta = self.get_variable(var_name)
            platform = var_meta.platform if var_meta else '_UNKNOWN_'
            groups[platform].append(var_name)
        return dict(groups)

    def get_duplicate_variables(self) -> List[VariableMetadata]:
        """获取所有跨表重复字段"""
        return [var for var in self.variables.values() if var.is_duplicate]

    def get_key_variables(self) -> List[VariableMetadata]:
        """获取所有疑似主键/通用字段"""
        return [var for var in self.variables.values() if var.is_likely_key]

    def get_variables_by_platform(self, platform: str) -> List[VariableMetadata]:
        """按平台查询变量"""
        return [var for var in self.variables.values() if var.platform == platform]

    def get_tables_by_category(self, category: str) -> List[TableMetadata]:
        """按分类查询表"""
        return [tbl for tbl in self.tables.values() if tbl.category == category]

    def get_tables_by_platform(self, platform: str) -> List[TableMetadata]:
        """按平台查询表"""
        return [tbl for tbl in self.tables.values() if tbl.platform == platform]

    def get_table_join_info(self, table_name: str) :
        """获取表的JOIN信息"""
        table = self.tables.get(table_name)
        if not table:
            return None
        return {
            'join_key': table.join_key,
            'partition_field': table.partition_field,
            'join_key_candidates': table.join_key_candidates,
            'category': table.category,
            'platform': table.platform
        }

    # ==================== 代理属性（访问拆分出的独立模块） ====================

    @property
    def classifier(self):
        """变量分类分析器（延迟初始化）"""
        if self._classifier is None:
            from src.metadata.variable_classifier import VariableClassifier
            self._classifier = VariableClassifier(self)
        return self._classifier

    @property
    def override_applier(self):
        """配置覆盖应用器（延迟初始化）"""
        if self._override_applier is None:
            from src.metadata.override_applier import OverrideApplier
            self._override_applier = OverrideApplier(self)
        return self._override_applier

    @property
    def statistics(self):
        """统计报告器（延迟初始化）"""
        if self._statistics is None:
            from src.metadata.metadata_statistics import MetadataStatistics
            self._statistics = MetadataStatistics(self)
        return self._statistics

    # ==================== 兼容代理方法（委托给独立模块） ====================

    def classify_variables(self, var_names: List[str]) -> Dict[str, List[str]]:
        """将变量按是否命中元数据进行分类"""
        return self.classifier.classify_variables(var_names)

    def find_ambiguous_variables(self, var_names: List[str]) -> Dict[str, List[str]]:
        """查找能同时匹配多张表的变量（歧义变量）"""
        return self.classifier.find_ambiguous_variables(var_names)

    def find_variable_sources(self, var_name: str) -> List[str]:
        """查找变量所在的所有来源表"""
        return self.classifier.find_variable_sources(var_name)

    def apply_variable_overrides(self, overrides: Dict[str, Dict[str, str]],
                                  table_join_keys: Optional[Dict[str, Dict[str, str]]] = None) -> None:
        """应用变量覆盖配置到元数据"""
        self.override_applier.apply_variable_overrides(overrides, table_join_keys)

    def apply_table_join_key_overrides(self, table_join_keys: Dict[str, Dict[str, str]]) -> None:
        """应用表关联键覆盖配置"""
        self.override_applier.apply_table_join_key_overrides(table_join_keys)

    def apply_variable_aliases(self, aliases: Dict[str, str]) -> None:
        """应用变量名别名映射到元数据"""
        self.override_applier.apply_variable_aliases(aliases)

    def get_statistics(self) -> Dict[str, Any]:
        """获取当前元数据的详细统计信息"""
        return self.statistics.get_statistics()

    def print_statistics(self) -> Dict[str, Any]:
        """打印元数据统计报告到控制台"""
        return self.statistics.print_statistics()

    def get_statistics_json(self) -> str:
        """将统计信息导出为JSON字符串"""
        return self.statistics.get_statistics_json()
