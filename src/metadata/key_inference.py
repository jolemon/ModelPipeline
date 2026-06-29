"""
主键推断模块

根据表名和分类推断 JOIN 关联键、候选键列表和分区字段。
同时提供主键/通用字段的检测功能。
"""

from typing import Tuple, List


# 疑似主键/通用字段集合（跨表重复时大概率是这些字段）
LIKELY_KEY_FIELDS: set = {
    'cust_id', 'cust_no', 'cert_no', 'cert_num', 'idcard', 'apply_no',
    'data_dt', 'dt', 'rpt_id', 'rpt_tm', 'report_no', 'reportno',
    'ci_rpt_id', 'pboc_bs61_073',
    'prd_big_cls_cd', 'prd_sub_cls_cd', 'prd_cd',
    'be_qry_nm', 'be_qry_cert_num', 'be_qry_cert_typ',
    'create_time', 'update_time', 'etl_dt', 'etl_date',
    'insert_time', 'modify_time', 'op_dt'
}


def infer_join_keys(table_name: str, category: str) -> Tuple[str, List[str], str]:
    """
    根据表名和分类推断主键关联

    Args:
        table_name: 表名
        category: 分类（行为变量/外部数据/征信变量/模型分）

    Returns:
        (join_key, join_key_candidates, partition_field)

    规则：
        1) 外部数据: cert_no/cert_num/idcard 优先，时间主键 dt
        2) 行为变量: cust_no/cust_id 优先，时间主键 dt
        3) 征信变量: 仅通过征信报告号 ci_rpt_id/report_no 关联
        4) 模型分: apply_no/cust_no/cert_no
    """
    tn_lower = table_name.lower()

    # 征信变量：仅通过征信报告号关联
    if category == '征信变量':
        candidates = ['ci_rpt_id', 'report_no', 'reportno', 'pboc_bs61_073']
        if 'zxysblhs' in tn_lower or 'zxbl' in tn_lower:
            primary = 'ci_rpt_id'
        elif 'pbci' in tn_lower:
            primary = 'report_no'
        else:
            primary = candidates[0]
        return primary, candidates, 'dt'

    # 行为变量：cust_no/cust_id + dt
    if category == '行为变量':
        candidates = ['cust_no', 'cust_id']
        return candidates[0], candidates, 'dt'

    # 模型分
    if category == '模型分':
        candidates = ['apply_no', 'cust_no', 'cert_no']
        return candidates[0], candidates, 'dt'

    # 百融表
    if 'br' in tn_lower or '百融' in table_name:
        candidates = ['cert_no', 'cert_num', 'idcard', 'apply_no']
        return candidates[0], candidates, 'dt'

    # 中征信
    if 'zx' in tn_lower or table_name == 'jsbrpt.v_ods_02_all_zzxqsf_md5':
        candidates = ['cert_no', 'cert_num', 'idcard', 'apply_no']
        return candidates[0], candidates, 'dt'

    # 平台类外部数据
    if table_name in ('京东', '腾讯', '度小满', '天创', '友盟', '同盾'):
        candidates = ['apply_no', 'cert_no', 'cust_no']
        return candidates[0], candidates, 'dt'

    # 其他外部数据兜底
    candidates = ['cert_no', 'cert_num', 'idcard', 'apply_no', 'cust_no']
    return candidates[0], candidates, 'dt'


def is_likely_key_field(var_name: str) -> bool:
    """
    判断字段是否可能是主键/通用字段而非业务变量

    Args:
        var_name: 变量名（应为小写）

    Returns:
        True 如果是疑似主键/通用字段
    """
    return var_name.lower() in LIKELY_KEY_FIELDS
