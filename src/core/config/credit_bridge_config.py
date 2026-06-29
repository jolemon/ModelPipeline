"""
征信桥接配置模块

职责：征信桥接表配置
"""

from datetime import datetime
from typing import Dict, Any


class CreditBridgeConfig:
    """征信桥接配置：征信主键表设置 + 桥接表名称生成"""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    @property
    def credit_primary_table(self) -> Dict[str, Any]:
        """征信主键表配置"""
        return self._config.get('credit_primary_table', {}) or {}

    @property
    def credit_bridge_enabled(self) -> bool:
        """征信桥接表功能是否启用"""
        return self.credit_primary_table.get('enabled', False)

    def get_credit_bridge_table_name(self, work_no: str, model_id: str,
                                      get_date_str_fn) -> str:
        """获取征信桥接表名称

        Args:
            work_no: 工作编号
            model_id: 模型编号
            get_date_str_fn: 生成日期字符串的函数

        Returns:
            桥接表名称，格式: tmp_${work_no}_${date}_${model_id}_PBCI
        """
        date_str = get_date_str_fn()
        return f"tmp_{work_no}_{date_str}_{model_id}_PBCI"
