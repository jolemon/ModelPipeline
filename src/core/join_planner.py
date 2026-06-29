"""
JOIN 策略规划器模块

基于元数据将多张表规划为合理的 JOIN 结构：
1. 按 (platform, join_key) 细粒度分组
2. 识别组内重复变量（同名但不同表）
3. 确定样本表到各分组的桥接字段
4. 超过 max_subquery_join 时自动拆分为多个子组

支持两种子组拆分策略：
- sequential: 顺序切分（先装满第一组）
- balanced: 均衡分配（尽量让每组子查询数量接近）
"""

from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from math import ceil

from src.metadata.manager import MetadataManager
from src.core.config_loader import SQLConfig
from src.core.models import TableGroup, JoinPlan


class JoinPlanner:
    """
    JOIN策略规划器

    基于metadata将74张表规划为合理的JOIN结构：
    1. 按 (platform, join_key) 细粒度分组
    2. 识别组内重复变量（同名但不同表）
    3. 确定样本表到各分组的桥接字段
    4. 超过max_subquery_join时自动拆分为多个子组
    """

    def __init__(self, metadata_manager: MetadataManager,
                 sql_config: Optional[SQLConfig] = None):
        """初始化JOIN策略规划器

        Args:
            metadata_manager: 元数据管理器，用于查询变量和表的映射关系
            sql_config: SQL配置对象（可选，默认使用config/config.yaml）
        """
        self.metadata = metadata_manager
        self.config = sql_config or SQLConfig()

    def _resolve_ambiguous_variables(self, model_features: List[str]) -> Dict[str, str]:
        """
        解析歧义变量，按平台规则确定最终来源表

        当行为变量存在多个候选关联表时：
        1. 如果 config.target_platform 匹配某个平台，优先选择该平台下的表
        2. 如果 target_platform 为空或不匹配，按 behavior_platform_priority 顺序选择

        Args:
            model_features: 入模变量列表

        Returns:
            {歧义变量名: 选定的来源表名}
        """
        ambiguous = self.metadata.find_ambiguous_variables(model_features)
        if not ambiguous:
            return {}

        resolved: Dict[str, str] = {}
        platform = self.config.target_platform
        priority_list = self.config.behavior_platform_priority

        for var_name, tables in ambiguous.items():
            table_metas = [
                self.metadata.get_table(t) for t in tables
                if self.metadata.get_table(t)
            ]

            # 只处理行为变量歧义
            behavior_metas = [
                tm for tm in table_metas
                if tm and tm.category == '行为变量'
            ]

            if not behavior_metas:
                resolved[var_name] = tables[0]
                continue
            if len(behavior_metas) == 1:
                resolved[var_name] = behavior_metas[0].table_name
                continue

            chosen = None
            if platform:
                for tm in behavior_metas:
                    if tm.platform == platform:
                        chosen = tm.table_name
                        break
            if not chosen:
                for p in priority_list:
                    for tm in behavior_metas:
                        if tm.platform == p:
                            chosen = tm.table_name
                            break
                    if chosen:
                        break
            if not chosen:
                chosen = behavior_metas[0].table_name

            resolved[var_name] = chosen

        return resolved

    def _split_tables(self, tables: List[str], max_join: int, strategy: str) -> List[List[str]]:
        """将表列表拆分为多个子组

        Args:
            tables: 源表名列表（已排序）
            max_join: 单组最大子查询数
            strategy: "sequential" 顺序切分 | "balanced" 均衡分配

        Returns:
            子组列表，每组包含若干表名
        """
        num_tables = len(tables)
        if num_tables <= max_join:
            return [tables]

        if strategy == "sequential":
            # 顺序切片：先装满第一组
            num_subgroups = ceil(num_tables / max_join)
            return [
                tables[i * max_join : min((i + 1) * max_join, num_tables)]
                for i in range(num_subgroups)
            ]

        elif strategy == "balanced":
            # 均衡分配：尽量让每组子查询数量接近
            num_subgroups = ceil(num_tables / max_join)
            base_size = num_tables // num_subgroups       # 每组基础大小
            remainder = num_tables % num_subgroups        # 前 remainder 组多1个

            result = []
            start = 0
            for i in range(num_subgroups):
                size = base_size + (1 if i < remainder else 0)
                result.append(tables[start : start + size])
                start += size
            return result

        else:
            raise ValueError(f"Unknown subgroup_strategy: {strategy}")

    def plan(self, model_features: List[str], sample_table: str,
             sample_key: str = "apply_no",
             sample_fields: Optional[List[str]] = None) -> JoinPlan:
        """
        规划JOIN策略

        Args:
            model_features: 入模变量列表（小写）
            sample_table: 样本表名
            sample_key: 样本表主键
            sample_fields: 样本表保留字段

        Returns:
            JoinPlan 执行计划
        """
        # 1. 解析歧义变量（按平台规则选择来源表）
        resolved_ambiguous = self._resolve_ambiguous_variables(model_features)

        # 2. 按表分组变量（使用解析后的结果）
        table_groups: Dict[str, List[str]] = defaultdict(list)
        for var_name in model_features:
            if var_name in resolved_ambiguous:
                table_groups[resolved_ambiguous[var_name]].append(var_name)
            else:
                var_meta = self.metadata.get_variable(var_name)
                if var_meta and var_meta.source_table:
                    table_groups[var_meta.source_table].append(var_name)
                else:
                    table_groups['_UNKNOWN_'].append(var_name)

        # 3. 按 (platform, join_key, time_range标记) 分组，并去重变量
        # 注意：配置了 time_range_joins 的表需要独立分组，因为它们的ON条件不同
        # 征信变量统一按 platform 分组（忽略 join_key 差异），使子查询分布更均匀
        platform_key_groups: Dict[Tuple, Dict[str, List[str]]] = defaultdict(dict)
        for table_name, variables in table_groups.items():
            if table_name == '_UNKNOWN_':
                continue

            table_meta = self.metadata.get_table(table_name)
            if not table_meta:
                continue

            platform = table_meta.platform or table_meta.category or 'other'
            join_key = table_meta.join_key or sample_key

            # 检查是否配置了时间区间匹配
            # 如果配置了，使用表名作为分组键的一部分，确保独立分组
            time_range_marker = ""
            if self.config.is_time_range_table(table_name):
                time_range_marker = f"_tr_{table_name}"

            # 去重变量（保持顺序）
            unique_vars = list(dict.fromkeys(variables))

            # 征信变量统一按 platform 分组（忽略 join_key 差异）
            # 这样同一平台下所有征信表会被均匀拆分到各子组
            # 征信变量统一使用 'ci_rpt_id' 作为组级 join_key
            # 注意："中征信"属于外部数据，使用其真实主键（cert_no），不走征信桥接
            is_credit = platform in self.config.credit_platforms
            if is_credit:
                platform_key_groups[(platform, 'ci_rpt_id', time_range_marker)][table_name] = unique_vars
            else:
                platform_key_groups[(platform, join_key, time_range_marker)][table_name] = unique_vars

        # 3. 构建TableGroup列表（考虑max_subquery_join拆分）
        groups = []
        max_join = self.config.max_subquery_join

        # 为每种变量类型维护独立的序号计数器（用于生成短别名）
        type_seq_counter: Dict[str, int] = defaultdict(int)
        date_str = self.config.get_date_str()

        for (platform, join_key, time_range_marker), table_vars in sorted(platform_key_groups.items()):
            platform_en = self.config.get_platform_en(platform)

            # 获取变量类型简称
            first_table = list(table_vars.keys())[0] if table_vars else None
            first_table_meta = self.metadata.get_table(first_table) if first_table else None
            category = first_table_meta.category if first_table_meta else 'unknown'
            var_type_en = self.config.get_var_type_en(category)
            var_type_short = self.config.get_var_type_short(var_type_en)

            tables = sorted(table_vars.keys())
            num_tables = len(tables)

            # 按策略拆分为多个子组
            subgroups = self._split_tables(tables, max_join, self.config.subgroup_strategy)

            for sub_tables in subgroups:
                sub_table_vars = {t: table_vars[t] for t in sub_tables}

                # 收集组内全部变量，检测重复
                var_counter: Dict[str, int] = defaultdict(int)
                all_vars = []
                for t, vars_list in sub_table_vars.items():
                    for v in vars_list:
                        var_counter[v] += 1
                        if v not in all_vars:
                            all_vars.append(v)

                duplicate_vars = {v for v, cnt in var_counter.items() if cnt > 1}

                # 生成短别名和临时表名
                type_seq_counter[var_type_short] += 1
                seq = type_seq_counter[var_type_short]
                safe_platform_en = platform_en.replace('-', '_')
                group_id = f"{safe_platform_en}_{seq}"  # 如 xj_pbci_1, zh_bh_1...

                # 根据命名风格生成临时表名
                if self.config.naming_style == 'descriptive':
                    # 描述性命名：使用平台+序号
                    safe_platform = platform_en.replace('-', '_')
                    temp_table_name = (
                        f"tmp_{self.config.work_no}_{date_str}_{self.config.model_id}_"
                        f"{safe_platform}_{seq:03d}"
                    )
                else:
                    # 简短命名
                    temp_table_name = (
                        f"tmp_{self.config.work_no}_{date_str}_{self.config.model_id}_"
                        f"{var_type_short}_{seq:03d}"
                    )

                group = TableGroup(
                    group_id=group_id,
                    platform=platform,
                    platform_en=platform_en,
                    join_key=join_key,
                    tables=sub_tables,
                    table_vars=sub_table_vars,
                    all_variables=all_vars,
                    duplicate_vars=duplicate_vars,
                    seq=seq,
                    temp_table_name=temp_table_name
                )
                groups.append(group)

        # 4. 确定桥接字段（样本表如何关联到各分组）
        bridge_keys = {}
        for g in groups:
            bridge_keys[g.group_id] = g.join_key

        # 5. 推断样本表别名
        sample_alias = self._infer_sample_alias(sample_table)

        return JoinPlan(
            sample_table=sample_table,
            sample_alias=sample_alias,
            sample_key=sample_key,
            sample_fields=sample_fields or [sample_key],
            groups=groups,
            bridge_keys=bridge_keys
        )

    def _infer_sample_alias(self, sample_table: str) -> str:
        """根据样本表名推断别名

        推断规则：
        1. 去掉数据库前缀（如 dwd.apply_info → apply_info）
        2. 去掉常见表前缀（tmp_, t_, dwd_, dws_, ads_, dim_, ods_ 等）
        3. 取第一个有意义单词的首字母作为别名
        4. 无法推断时回退到 's'

        Args:
            sample_table: 样本表全名

        Returns:
            推断出的单字母别名
        """
        # 去掉数据库前缀
        table_name = sample_table.split('.')[-1]

        # 常见前缀列表（按优先级排序）
        prefixes = ('tmp_', 't_', 'dwd_', 'dws_', 'ads_', 'dim_', 'ods_', 'stg_')
        for prefix in prefixes:
            if table_name.startswith(prefix):
                table_name = table_name[len(prefix):]
                break

        # 取第一个有意义单词的首字母
        if table_name:
            first_char = table_name[0].lower()
            if first_char.isalpha():
                return first_char

        return "s"
