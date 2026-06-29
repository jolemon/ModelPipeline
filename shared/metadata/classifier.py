"""
元数据分类器

根据表名自动推断变量的分类（category）和平台（platform）。
这些规则是项目核心资产，被 metadata manager 和 converter 共同使用。
"""

from typing import Optional


def classify_category(table_name: str) -> str:
    """
    特征大类分类：行为变量 / 外部数据 / 征信变量 / 模型分

    Args:
        table_name: 来源表名

    Returns:
        分类字符串，无法识别时返回空字符串
    """
    if not table_name or not isinstance(table_name, str):
        return ''

    tn_lower = table_name.lower()

    # 行为变量
    if (tn_lower.startswith('wdyy.t_ccr') or
        tn_lower.startswith('wdyy.c01_ccr') or
        tn_lower.startswith('wdyy_mrs.t_cc') or
        tn_lower.startswith('t_cc_cust') or
        tn_lower.startswith('wdyy.t_cc_cust') or
        tn_lower.startswith('ads.ads_risk_')):
        return '行为变量'

    # 征信变量
    if (tn_lower.startswith('t_pbci') or
        tn_lower.startswith('wdyy_mrs.t_pbci') or
        tn_lower.startswith('wdyy.t_zxysblhs') or
        tn_lower.startswith('wdyy.v_md5_t_zxysblhs') or
        tn_lower.startswith('jsbrpt_mrs.zxbl_his')):
        return '征信变量'

    # 模型分
    if tn_lower.startswith('sykj1.model'):
        return '模型分'

    # 外部数据（EDAP / 特定表 / 平台名）
    if (tn_lower.startswith('edap.') or
        tn_lower.startswith('ed') or
        tn_lower.startswith('ned') or
        table_name in ('度小满', '京东', '腾讯', '天创', '友盟', '同盾') or
        table_name == 'jsbrpt.v_ods_02_all_zzxqsf_md5' or
        tn_lower.startswith('jsbrpt_mrs.ods_02_all_zzxqsf') or
        table_name == 'unknown.unknown'):
        return '外部数据'

    return ''


def classify_platform(table_name: str) -> str:
    """
    平台二级分类

    Args:
        table_name: 来源表名

    Returns:
        平台名称，无法识别时返回空字符串
    """
    if not table_name or not isinstance(table_name, str):
        return ''

    tn_lower = table_name.lower()

    # 百融
    if tn_lower.startswith('edap.v_br') or tn_lower.startswith('edap.v_fqz_br'):
        return '百融'

    # 字节
    if (tn_lower.startswith('wdyy.t_ccrdyyf') or
        tn_lower.startswith('wdyy.c01_ccrdyyf') or
        tn_lower.startswith('ned772')):
        return '字节'

    # 京东白条
    if tn_lower.startswith('wdyy.t_ccrbt') or tn_lower.startswith('wdyy_mrs.t_ccrbt'):
        return '京东白条'

    # 直接平台名
    if table_name in ('度小满', '京东', '腾讯', '天创', '友盟', '同盾'):
        return table_name

    # 中征信（芝麻信用）
    if table_name == 'jsbrpt.v_ods_02_all_zzxqsf_md5' or tn_lower.startswith('jsbrpt_mrs.ods_02_all_zzxqsf'):
        return '中征信'

    # 天辰
    if tn_lower.startswith('ed0509'):
        return '天辰'

    # 友盟
    if tn_lower.startswith('ned0535'):
        return '友盟'

    # 度小满
    if tn_lower.startswith('ed0223'):
        return '度小满'

    # 同盾
    if tn_lower.startswith('ed0076'):
        return '同盾'

    # 贷中行为变量-新底座
    if tn_lower.startswith('ads.ads_risk_'):
        return '贷中行为变量-新底座'

    # 行为变量-消金
    if table_name == 'wdyy.T_CC_CUST_BEHAV_VARBL_INDEX':
        return '行为变量-消金'

    # 行为变量-总行
    if (tn_lower.startswith('t_cc_cust') or
        tn_lower.startswith('wdyy.t_cc_cust') or
        tn_lower.startswith('wdyy_mrs.t_cc_cust')):
        return '行为变量-总行'

    # 征信变量-消金
    if (tn_lower.startswith('wdyy.t_zxysblhs') or
        tn_lower.startswith('wdyy.v_md5_t_zxysblhs') or
        tn_lower.startswith('jsbrpt_mrs.zxbl_his')):
        return '征信变量-消金'

    # 征信变量-总行
    if tn_lower.startswith('t_pbci') or tn_lower.startswith('wdyy_mrs.t_pbci'):
        return '征信变量-总行'

    # 模型分
    if tn_lower.startswith('sykj1.model'):
        return '模型分'
    if table_name == '暂无':
        return '模型分'

    # 兜底
    if tn_lower.startswith('edap.') or tn_lower.startswith('ed'):
        return '外部数据'
    if tn_lower.startswith('ned'):
        return '外部数据'
    if table_name == 'unknown.unknown':
        return '度小满'

    return ''


def classify_fallback(table_name: str, platform: str) -> str:
    """
    当 classify_category 返回空时的 fallback 推断

    根据 platform 推断 category。

    Args:
        table_name: 来源表名
        platform: 已推断的平台

    Returns:
        分类字符串
    """
    if not platform:
        return '未知'

    if platform in ('百融', '京东白条', '中征信', '天辰', '友盟',
                     '度小满', '京东', '腾讯', '天创', '同盾', '外部数据'):
        return '外部数据'
    if '征信' in platform:
        return '征信变量'
    if '行为' in platform:
        return '行为变量'
    if platform == '模型分':
        return '模型分'

    return '未知'
