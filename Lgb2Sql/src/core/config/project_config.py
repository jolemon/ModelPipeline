"""
项目配置模块

职责：项目基本信息 + 日期/命名映射工具
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any


class ProjectConfig:
    """项目配置：工作编号、模型信息、日期/命名工具"""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    @property
    def work_no(self) -> str:
        """工作编号"""
        return self._config.get('project', {}).get('work_no', 'FX0000')

    @property
    def model_id(self) -> str:
        """模型编号"""
        return self._config.get('project', {}).get('model_id', 'M000')

    @property
    def date_format(self) -> str:
        """日期格式"""
        return self._config.get('project', {}).get('date_format', 'yyyyMMdd')

    @property
    def target_platform(self) -> str:
        """目标平台（用于歧义变量解析时优先匹配该平台下的表）"""
        return self._config.get('project', {}).get('target_platform', '')

    @property
    def platform_alias(self) -> str:
        """平台别名（用于替换表名中的 $platform 占位符）"""
        return self._config.get('project', {}).get('platform_alias', '')

    @property
    def behavior_platform_priority(self) -> List[str]:
        """行为变量平台优先级列表（当platform不匹配时使用）"""
        return self._config.get('behavior_platform_priority', [
            "贷中行为变量-新底座",
            "行为变量-总行",
            "行为变量-消金",
            "字节",
            "京东白条"
        ])

    def get_date_str(self, date: Optional[datetime] = None) -> str:
        """生成日期字符串"""
        d = date or datetime.now()
        fmt = self.date_format
        fmt = fmt.replace('yyyy', '%Y').replace('MM', '%m').replace('dd', '%d')
        return d.strftime(fmt)

    def resolve_table_name(self, table_name: str) -> str:
        """解析表名，替换 $platform 占位符"""
        if not table_name or '$platform' not in table_name:
            return table_name
        return table_name.replace('$platform', self.platform_alias)

    def get_var_type_en(self, category: str) -> str:
        """获取变量类型的英文映射"""
        mapping = self._config.get('var_type_mapping', {})
        return mapping.get(category, 'unknown')

    def get_platform_en(self, platform: str) -> str:
        """获取平台的英文映射"""
        mapping = self._config.get('platform_mapping', {})
        return mapping.get(platform, 'unknown')

    def get_var_type_short(self, var_type_en: str) -> str:
        """获取变量类型英文简称（用于临时表命名）"""
        mapping = {
            'behavior': 'bh',
            'credit': 'pbci',
            'external': 'wd',
            'modelscore': 'ms',
            'unknown': 'unk'
        }
        return mapping.get(var_type_en, 'unk')

    def get_alias_prefix(self, var_type_en: str) -> str:
        """获取SQL别名前缀（用于SELECT中的表别名）"""
        mapping = {
            'behavior': 'bh',
            'credit': 'p',
            'external': 'ext',
            'modelscore': 'ms',
            'unknown': 'u'
        }
        return mapping.get(var_type_en, 'u')

    def generate_temp_table_name(self, var_type_en: str, seq: int,
                                  date: Optional[datetime] = None) -> str:
        """生成临时表名称"""
        date_str = self.get_date_str(date)
        return f"tmp_{self.work_no}_{date_str}_{self.model_id}_{var_type_en}_{seq:03d}"

    def generate_group_id(self, platform_en: str, join_key: str) -> str:
        """生成分组标识（英文）"""
        safe_platform = re.sub(r'[^a-zA-Z0-9_]', '_', platform_en)
        safe_key = re.sub(r'[^a-zA-Z0-9_]', '_', join_key)
        return f"{safe_platform}_{safe_key}"
