"""
Excel数据字典转YAML模块
功能：将Excel格式的变量数据字典转换为YAML格式的变量元数据

Excel格式要求：
字段名 | 字段含义 | 来源表 | 表描述
-------|---------|--------|--------
als_m12_id_nbank_max_monnum | 近12个月非银最大月申请次数 | edap.v_BRDT_APPLYLOANSTR_md5 | 百融多头变量
"""

import pandas as pd
import yaml
from pathlib import Path
from typing import Union, Optional, Dict, List
from collections import defaultdict


class ExcelToYamlConverter:
    """
    Excel转YAML转换器
    
    将Excel数据字典转换为结构化的YAML元数据文件
    """
    
    # Excel默认列名映射
    DEFAULT_COLUMN_MAP = {
        'var_name': '字段名',
        'var_desc': '字段含义',
        'source_table': '来源表',
        'table_desc': '表描述',
        'category': '分类',
        'partition_field': '分区字段',
        'join_key': '关联主键'
    }
    
    def __init__(
        self,
        column_map: Optional[Dict[str, str]] = None,
        default_partition: str = "dt",
        default_join_key: str = "apply_no"
    ):
        """
        初始化转换器
        
        Args:
            column_map: 列名映射，如 {'var_name': '字段名', ...}
            default_partition: 默认分区字段
            default_join_key: 默认关联主键
        """
        self.column_map = column_map or self.DEFAULT_COLUMN_MAP.copy()
        self.default_partition = default_partition
        self.default_join_key = default_join_key
        
    def convert(
        self,
        excel_path: Union[str, Path],
        sheet_name: Union[str, int] = 0,
        output_path: Optional[Union[str, Path]] = None,
        category_map: Optional[Dict[str, str]] = None
    ) -> dict:
        """
        转换Excel为YAML数据
        
        Args:
            excel_path: Excel文件路径
            sheet_name: 工作表名或索引
            output_path: YAML输出路径（不提供则只返回数据不保存）
            category_map: 表名到分类的映射，如 {'edap.v_BRDT': '外数', 'edap.v_credit': '征信'}
            
        Returns:
            YAML数据字典
        """
        # 读取Excel
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        
        # 标准化列名
        df = self._normalize_columns(df)
        
        # 构建变量列表
        variables = []
        tables = defaultdict(lambda: {
            'table_desc': '',
            'variables': [],
            'category': '',
            'partition_field': self.default_partition,
            'join_key': self.default_join_key
        })
        
        for _, row in df.iterrows():
            var_record = self._build_variable_record(row, category_map)
            variables.append(var_record)
            
            # 同时构建表分组
            table_name = var_record.get('source_table', '')
            if table_name:
                tables[table_name]['variables'].append(var_record['var_name'])
                tables[table_name]['table_desc'] = var_record.get('table_desc', '')
                tables[table_name]['category'] = var_record.get('category', '')
                if var_record.get('partition_field'):
                    tables[table_name]['partition_field'] = var_record['partition_field']
                if var_record.get('join_key'):
                    tables[table_name]['join_key'] = var_record['join_key']
        
        # 构建输出结构
        yaml_data = {
            'metadata_info': {
                'source': str(excel_path),
                'total_variables': len(variables),
                'total_tables': len(tables)
            },
            'variables': variables,
            'tables': [
                {
                    'table_name': name,
                    'table_desc': info['table_desc'],
                    'category': info['category'],
                    'partition_field': info['partition_field'],
                    'join_key': info['join_key'],
                    'variables': info['variables']
                }
                for name, info in sorted(tables.items())
            ]
        }
        
        # 保存YAML
        if output_path:
            self._save_yaml(yaml_data, output_path)
        
        return yaml_data
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化DataFrame列名
        
        将中文列名映射为英文标准名
        """
        # 创建反向映射
        reverse_map = {v: k for k, v in self.column_map.items()}
        
        # 重命名列
        new_columns = {}
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in reverse_map:
                new_columns[col] = reverse_map[col_str]
        
        df = df.rename(columns=new_columns)
        
        # 确保必要列存在
        required = ['var_name', 'source_table']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Excel缺少必要列: {self.column_map.get(col, col)}")
        
        return df

    def _build_variable_record(
        self,
        row: pd.Series,
        category_map: Optional[Dict[str, str]] = None
    ) -> dict:
        """
        构建单条变量记录
        
        Args:
            row: DataFrame行
            category_map: 分类映射
            
        Returns:
            变量记录字典
        """
        var_name = str(row.get('var_name', '')).strip()
        source_table = str(row.get('source_table', '')).strip()
        
        # 推断分类
        category = str(row.get('category', '')).strip()
        if not category and category_map:
            for prefix, cat in category_map.items():
                if prefix in source_table:
                    category = cat
                    break
        
        record = {
            'var_name': var_name,
            'var_desc': str(row.get('var_desc', '')).strip(),
            'source_table': source_table,
            'table_desc': str(row.get('table_desc', '')).strip(),
            'category': category,
            'partition_field': str(row.get('partition_field', self.default_partition)).strip(),
            'join_key': str(row.get('join_key', self.default_join_key)).strip()
        }
        
        return record
    
    def _save_yaml(self, data: dict, output_path: Union[str, Path]) -> None:
        """
        保存为YAML文件
        
        Args:
            data: 数据字典
            output_path: 输出路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                data,
                f,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
                indent=2
            )
        
        print(f"YAML已保存到: {output_path}")
    
    @staticmethod
    def infer_category_from_table(table_name: str) -> str:
        """
        根据表名推断变量分类
        
        规则：
        - 包含 credit/征信 -> 征信
        - 包含 behavior/行为 -> 行为
        - 包含 brdt/百融/外部 -> 外数
        
        Args:
            table_name: 表名
            
        Returns:
            分类名称
        """
        name_lower = table_name.lower()
        
        if any(k in name_lower for k in ['credit', '征信', 'pboc', '百行']):
            return '征信'
        elif any(k in name_lower for k in ['behavior', '行为', 'act', 'action']):
            return '行为'
        elif any(k in name_lower for k in ['brdt', '百融', '外部', 'external', 'third']):
            return '外数'
        else:
            return '其他'


def convert_excel_to_yaml(
    excel_path: Union[str, Path],
    output_path: Union[str, Path],
    sheet_name: Union[str, int] = 0,
    **kwargs
) -> dict:
    """
    便捷函数：Excel转YAML
    
    Args:
        excel_path: Excel文件路径
        output_path: YAML输出路径
        sheet_name: 工作表名
        **kwargs: 传递给转换器的其他参数
        
    Returns:
        YAML数据字典
    """
    converter = ExcelToYamlConverter(**kwargs)
    return converter.convert(excel_path, sheet_name, output_path)
