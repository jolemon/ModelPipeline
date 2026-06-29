from model_library.config import *
import pandas as pd
from sklearn.model_selection import train_test_split
import numpy as np
import toad
from toad.stats import feature_bin_stats
from scipy import stats
import time


def fillna_strategy(df, feature_columns):
    # 动态生成填充字典
    fillna_dict = {}
    
    for col in feature_columns:
        col_type = df[col].dtype
        if col_type in ['int64', 'float64']:
            # 数值型列：使用均值填充
            fillna_dict[col] = -999999.0
        elif col_type == 'object' or col_type.name == 'category':
            # 分类列：使用众数填充
            fillna_dict[col] = df[col].mode()[0] if not df[col].mode().empty else 'Unknown'
            print('============================', col, fillna_dict[col])
        elif col_type == 'datetime64[ns]':
            # 时间列：使用前向填充
            fillna_dict[col] = df[col].ffill().iloc[-1]  # 若最后仍为 NaN，则用最后一个有效值填充
    # print(fillna_dict, '============================')
    return fillna_dict


def calc_missing(df, feature_columns): 
    #缺失率统计
    test_dataset = df.copy()
    for col in feature_columns:
        try:
            test_dataset[col] = test_dataset[col].astype(float64)
            test_dataset.loc[test_dataset[col] <= -9999, col]=np.nan
        except:
            pass
    overall_distribution=toad.detect(test_dataset[feature_columns]).reset_index()
    return overall_distribution


def calc_psi(df, feature_columns, sample_date='encash_date', split_partid='202412'):
    #psi统计
    df = df.copy()
    # df['loan_month'] = df[sample_date].apply(lambda x:str(x)[0:6])
    df['loan_month'] = df[sample_date].astype(str).apply(lambda x: x.replace('-', '')[0:6])
    data_train=df[(df['loan_month']<=split_partid)]
    data_oot=df[(df['loan_month']>split_partid)]
    overall_psi_stat=toad.metrics.PSI(data_train[feature_columns],data_oot[feature_columns]).reset_index()
    overall_psi_stat.columns=['index','psi']
    return overall_psi_stat


def calc_iv(df, feature_columns, label='target_mob6_30'): 
    # iv统计
    overall_iv=toad.quality(df[feature_columns+[label]], label, iv_only=True).reset_index()
    return overall_iv 


def calculate_ks(df, variable, target='target_mob6_30', bins=10):
    # 分箱（等频分箱）
    df['bin'] = pd.qcut(df[variable], q=bins, duplicates='drop')
    
    # 按分箱统计好坏样本数
    grouped = df.groupby('bin')[target].agg(['count', 'sum'])
    grouped['good'] = grouped['count'] - grouped['sum']
    total_bad = grouped['sum'].sum()
    total_good = grouped['good'].sum()
    
    # 计算累积占比
    grouped['bad_cum'] = grouped['sum'].cumsum() / total_bad
    grouped['good_cum'] = grouped['good'].cumsum() / total_good
    
    # 计算KS
    grouped['ks'] = abs(grouped['bad_cum'] - grouped['good_cum'])
    ks_max = grouped['ks'].max()
    
    return ks_max, grouped[['count', 'sum', 'good', 'bad_cum', 'good_cum', 'ks']]


def get_feature_warehouse():
    #特征库
    feature_warehouse = pd.read_excel(feature_warehouse_path)
    feature_warehouse['字段名'] = feature_warehouse['字段名'].apply(str.lower)
    return feature_warehouse


def split_dataset(dataset, target='target_mob6_30', train_split_size=0.8, random_state=2025):
    # 按时间切分开发 跨时间样本
    dataset[part_id] = dataset[sample_date].astype(str).apply(lambda x: x.replace('-', '')[0:6])
    dataset[dataflag]=dataset[part_id].apply(lambda x: dataflag_train if x < oot_start_part_id else dataflag_oot) #按时间切分开发 跨时间样本
    
    train_set=dataset[(dataset[dataflag]==dataflag_train)]
    oot_set=dataset[(dataset[dataflag]==dataflag_oot)]
    
    x_train, x_test, y_train, y_test = train_test_split(train_set, train_set[target], test_size=1.0 - train_split_size, random_state=random_state, stratify=train_set[target]) 
    x_oot, y_oot= oot_set, oot_set[target] 
    
    x_test.loc[:, dataflag] = dataflag_test
    x_all = pd.concat([x_train.reset_index(), x_test.reset_index(), x_oot.reset_index()], axis=0).drop(['index'],axis=1) 
    y_all = pd.concat([y_train,y_test,y_oot], axis=0).reset_index().drop(['index'],axis=1)

    return x_train, x_test, x_oot, x_all, y_train, y_test, y_oot, y_all

#psi统计 等频分箱
def calc_psi_qcut(df, feature_columns, sample_date='encash_date', split_partid='202412', bins_num=5):
    df = df.copy()
    df['loan_month'] = df[sample_date].astype(str).apply(lambda x: x.replace('-', '')[0:6])
    data_train=df[(df['loan_month']<=split_partid)]
    data_oot=df[(df['loan_month']>split_partid)]   
    psi_list, q_psi_list, ds_psi_list, ds_q_psi_list = [], [], [], []
    for feat in feature_columns: 
        expected_data = data_train[feat]
        actual_data = data_oot[feat]
        # 等频分箱
        q_bin_edges = pd.qcut(expected_data, q=bins_num, retbins=True, duplicates='drop')[1]
        
        q_expected_binned = pd.cut(expected_data, bins=q_bin_edges)
        q_actual_binned = pd.cut(actual_data, bins=q_bin_edges)
        
        q_psi, frame = toad.metrics.PSI(q_actual_binned, q_expected_binned, return_frame=True)
        q_psi_list.append(q_psi)
        print('frame: ', feat)
        frame['psi_'] = (frame['test'] - frame['base']) * np.log(frame['test'] / frame['base'])
        frame = frame[['value', 'base', 'test', 'psi_']]
        print(frame) 
        print('psi: ', q_psi)
 
        # 等宽分箱
        bin_edges = pd.cut(expected_data, bins=bins_num, retbins=True)[1]  # 获取分箱边界
        expected_binned = pd.cut(expected_data, bins=bin_edges)
        actual_binned = pd.cut(actual_data, bins=bin_edges) 
        psi = toad.metrics.PSI(actual_binned, expected_binned) 
        psi_list.append(psi) 
         
    return pd.DataFrame({
        'var': feature_columns, 
        'psi': psi_list, 
        'q_psi':q_psi_list
    }) 


# 合并特征的缺失率、PSI、IV
def get_feature_attr(overall_distribution, overall_psi_stat, overall_iv):
    feature_ls,missing_ls,psi_ls,iv_ls=[],[],[],[]
    for f in overall_iv['index'].tolist():
        feature_ls.append(f)
        missing_ls.append(float(str(overall_distribution[overall_distribution['index']==f]['missing'].iloc[0]).strip('%'))/100)
        psi_ls.append(overall_psi_stat[overall_psi_stat['index']==f]['psi'].iloc[0])
        iv_ls.append(overall_iv[overall_iv['index']==f]['iv'].iloc[0])
    final_feature_df=pd.DataFrame({'feature':feature_ls,'missing':missing_ls,'psi':psi_ls,'iv':iv_ls}).sort_values(by='iv',ascending=False)
    return final_feature_df


# 默认值为最宽松，如果不设置，相当于该项不做不过滤
def filter_feature(feature_df, missing_threshold_max=1.0, iv_threshold_min=0.0, psi_threshold_max=1.0):
    filter_feature_df = feature_df[(feature_df['missing'] <= missing_threshold_max) & \
                                (feature_df['iv'] >= iv_threshold_min) & \
                                (feature_df['psi'] <= psi_threshold_max)]
    return filter_feature_df


    
def do_feature_category_classify(table_name):
    if not table_name or type(table_name) != str:
        return ''
    if table_name.lower().startswith('wdyy.t_ccr') or table_name.lower().startswith('wdyy.c01_ccr') or \
       table_name.lower().startswith('t_cc_cust') or table_name.lower().startswith('wdyy.t_cc_cust') or \
       table_name.lower().startswith('ads.ads_risk_'):
        return '行为变量'
    if table_name.lower().startswith('edap.') or table_name == 'jsbrpt.v_ods_02_all_zzxqsf_md5' or \
       table_name in ['度小满', '京东', '腾讯', '天创', '友盟', '同盾']:
        return '外部数据' 
    if table_name.lower().startswith('t_pbci') or table_name.lower().startswith('wdyy.t_zxysblhs') or \
       table_name.lower().startswith('wdyy.v_md5_t_zxysblhs') or table_name.lower().startswith('jsbrpt_mrs.zxbl_his'):
        return '征信变量'
    if table_name.lower().startswith('sykj1.model'):
        return '模型分'
    return ''


def do_platform_classify(table_name):
    if not table_name or type(table_name) != str:
        return ''
    
    if table_name.lower().startswith('edap.v_br') or table_name.lower().startswith('edap.v_fqz_br'):
        return '百融'
    if table_name.lower().startswith('wdyy.t_ccrdyyf') or table_name.lower().startswith('wdyy.c01_ccrdyyf') or table_name.lower().startswith('ned772'):
        return '字节'
    if table_name.lower().startswith('wdyy.t_ccrbt'):
        return '京东白条'
    if table_name in ['度小满', '京东', '腾讯', '天创', '友盟', '同盾']:
        return table_name
    if table_name == 'jsbrpt.v_ods_02_all_zzxqsf_md5':
        return '中征信'
    if table_name.lower().startswith('ed0509'):
        return '天辰'
    if table_name.lower().startswith('ned0535'):
        return '友盟'
    if table_name.lower().startswith('ed0223'):
        return '度小满'
    if table_name.lower().startswith('edap.') or  table_name.lower().startswith('ed') :
        return '外部数据'
    if table_name.lower().startswith('ads.ads_risk_'):
        return '贷中行为变量-新底座'
    if table_name == 'wdyy.T_CC_CUST_BEHAV_VARBL_INDEX':
        return '行为变量-消金'
    if table_name.lower().startswith('t_cc_cust') or table_name.lower().startswith('wdyy.t_cc_cust'):
        return '行为变量-总行'
    if table_name.lower().startswith('wdyy.t_zxysblhs') or table_name.lower().startswith('wdyy.v_md5_t_zxysblhs') or \
       table_name.lower().startswith('jsbrpt_mrs.zxbl_his'):
        return '征信变量-消金' 
    if table_name.lower().startswith('t_pbci'):
        return '征信变量-总行' 
    return ''


def get_data_warehouse(new_base=False): 
    if new_base:
        feature_warehouse = pd.read_excel(os.path.join(data_warehouse_dir, feature_warehouse_file_name_newbase))
    else:   
        feature_warehouse = pd.read_excel(os.path.join(data_warehouse_dir, feature_warehouse_file_name))
    feature_warehouse['字段名'] = feature_warehouse['字段名'].astype(str).apply(str.lower) 
    feature_warehouse['类型'] = feature_warehouse['来源表'].apply(lambda x: do_feature_category_classify(x))
    feature_warehouse['平台'] = feature_warehouse['来源表'].apply(lambda x: do_platform_classify(x))
    return feature_warehouse



def calculate_monthly_coverage(dataset, dt_col='dt', exclude_cols=None, to_csv_path=None):
    """
    分月统计各个特征的覆盖率
    
    Parameters:
    -----------
    dataset : pd.DataFrame
        输入的数据集
    dt_col : str
        时间分片列名，默认为'dt'
    exclude_cols : list
        需要排除的列名列表（如ID列等），默认为None
    
    Returns:
    --------
    pd.DataFrame
        各月份各特征的覆盖率统计表
    """
    
    # 复制数据避免修改原数据
    df = dataset.copy()
    
    
    # 确定要统计的特征列（排除时间列和指定的排除列）
    if exclude_cols is None:
        exclude_cols = []
    
    exclude_cols = list(set(exclude_cols + [dt_col]))
    feature_cols = [col for col in df.columns 
                    if col not in exclude_cols and col != 'dt']
    
    # 按年月分组统计覆盖率
    coverage_results = []
    
    for month, month_data in df.groupby('dt'):
        month_coverage = {'dt': str(month)}
        total_records = len(month_data)
        
        for col in feature_cols:
            # 计算覆盖率（非空值比例）
            if pd.api.types.is_numeric_dtype(month_data[col]):
                # 对于数值型特征，可以定义为非空且非NaN的比例
                non_null_count = month_data[col].notna().sum()
                coverage = non_null_count / total_records if total_records > 0 else 0
            else:
                # 对于非数值型，使用非空比例
                non_null_count = month_data[col].notna().sum()
                coverage = non_null_count / total_records if total_records > 0 else 0
            
            month_coverage[f'{col}'] = coverage
        
        coverage_results.append(month_coverage)
    
    # 转换为DataFrame
    coverage_df = pd.DataFrame(coverage_results)
    
    # 按年月排序
    coverage_df = coverage_df.sort_values('dt')

    if to_csv_path:
        coverage_df.to_csv(to_csv_path, index=False)
    
    return coverage_df



def monotonic_binning(dataset, feat, target='target', good=0, bad=1,
                      missing_values=[-999999, -999], min_samples_pct=0.05, max_samples_pct=0.5,
                      monotonic='increase'):
    """
    对数值型特征分箱，满足：
    1. NaN 和 missing_values 单独作为一箱（min/max = "MISSING_VALUE"）
    2. 有效值分箱数 ≥ 3
    3. 每箱样本占比（占总样本）在 [min_samples_pct, max_samples_pct] 之间
    4. 有效分箱的 WOE 单调（increase 或 decrease）

    返回 DataFrame，列：min, max, goods, bads, total, good_prop, bad_prop, bad_rate, woe, iv, ks, lift

    
    # 使用示例
    # result = monotonic_binning(dataset, 'age', target='target')
    # result
    """
    df = dataset[[feat, target]].copy()
    total_n = len(df)

    # ---------- 1. 分离缺失/特殊值 ----------
    special_mask = df[feat].isna() | df[feat].isin(missing_values)
    valid_mask = ~special_mask
    valid_data = df.loc[valid_mask, feat]
    valid_target = df.loc[valid_mask, target]

    if len(valid_data) == 0:
        raise ValueError("有效值数量为0，无法分箱")

    # ---------- 2. 对有效值进行初始细粒度等频分箱 ----------
    n_init = 20
    if len(valid_data) < n_init * 10:
        n_init = max(5, len(valid_data) // 10)
    percentiles = np.linspace(0, 100, n_init + 1)[1:-1]
    init_bins = np.percentile(valid_data, percentiles)
    init_bins = np.unique(init_bins)
    bin_edges = np.concatenate(([-np.inf], init_bins, [np.inf]))
    bin_idx = np.digitize(valid_data, bin_edges) - 1

    micro_stats = []
    for i in range(len(bin_edges)-1):
        mask = (bin_idx == i)
        if mask.sum() == 0:
            continue
        goods = (valid_target[mask] == good).sum()
        bads = (valid_target[mask] == bad).sum()
        total = mask.sum()
        micro_stats.append({
            'bin_id': i,
            'min': bin_edges[i],
            'max': bin_edges[i+1],
            'goods': goods,
            'bads': bads,
            'total': total
        })
    micro_df = pd.DataFrame(micro_stats)

    # ---------- 3. 合并微箱以满足占比约束 ----------
    total_good = (df[target] == good).sum()
    total_bad = (df[target] == bad).sum()
    overall_bad_rate = total_bad / total_n

    micro_df['total_pct'] = micro_df['total'] / total_n
    final_bins = []
    current = {'min': None, 'max': None, 'goods': 0, 'bads': 0, 'total': 0}
    for idx, row in micro_df.iterrows():
        if current['min'] is None:
            current['min'] = row['min']
        current['max'] = row['max']
        current['goods'] += row['goods']
        current['bads'] += row['bads']
        current['total'] += row['total']
        cur_pct = current['total'] / total_n
        if cur_pct > max_samples_pct:
            if current['total'] == row['total']:
                print(f"警告：单个微箱占比 {cur_pct:.2%} 超过上限 {max_samples_pct:.0%}，将保留")
                final_bins.append(current.copy())
                current = {'min': None, 'max': None, 'goods': 0, 'bads': 0, 'total': 0}
            else:
                current['goods'] -= row['goods']
                current['bads'] -= row['bads']
                current['total'] -= row['total']
                final_bins.append(current.copy())
                current = {'min': row['min'], 'max': row['max'], 'goods': row['goods'], 'bads': row['bads'], 'total': row['total']}
        elif cur_pct >= min_samples_pct:
            final_bins.append(current.copy())
            current = {'min': None, 'max': None, 'goods': 0, 'bads': 0, 'total': 0}
    if current['total'] > 0:
        if current['total'] / total_n < min_samples_pct and len(final_bins) > 0:
            last = final_bins[-1]
            last['max'] = current['max']
            last['goods'] += current['goods']
            last['bads'] += current['bads']
            last['total'] += current['total']
        else:
            final_bins.append(current)

    if len(final_bins) < 2:
        raise ValueError(f"有效分箱数不足2（当前{len(final_bins)}），请调整分箱参数")

    # ---------- 4. 计算每个箱的指标 ----------
    def compute_metrics(bin_list):
        bin_stats = []
        for b in bin_list:
            goods = b['goods']
            bads = b['bads']
            total = b['total']
            good_prop = goods / total_good if total_good > 0 else 0
            bad_prop = bads / total_bad if total_bad > 0 else 0
            bad_rate = bads / total if total > 0 else 0
            eps = 1e-10
            good_prop = max(good_prop, eps)
            bad_prop = max(bad_prop, eps)
            woe = np.log(bad_prop / good_prop)
            iv = (bad_prop - good_prop) * woe
            ks = abs(bad_prop - good_prop)
            lift = bad_rate / overall_bad_rate if overall_bad_rate > 0 else np.inf
            bin_stats.append({
                'min': b['min'],
                'max': b['max'],
                'goods': goods,
                'bads': bads,
                'total': total,
                'good_prop': good_prop,
                'bad_prop': bad_prop,
                'bad_rate': bad_rate,
                'woe': woe,
                'iv': iv,
                'ks': ks,
                'lift': lift
            })
        return pd.DataFrame(bin_stats)

    df_valid_bins = compute_metrics(final_bins)

    # ---------- 5. 强制 WOE 单调性 ----------
    def is_monotonic(series, direction='increase'):
        if direction == 'increase':
            return all(series[i] <= series[i+1] for i in range(len(series)-1))
        else:
            return all(series[i] >= series[i+1] for i in range(len(series)-1))

    max_iter = 10
    for _ in range(max_iter):
        woe_vals = df_valid_bins['woe'].values
        if is_monotonic(woe_vals, monotonic):
            break
        merge_idx = -1
        if monotonic == 'increase':
            for i in range(len(woe_vals)-1):
                if woe_vals[i] > woe_vals[i+1]:
                    merge_idx = i
                    break
        else:
            for i in range(len(woe_vals)-1):
                if woe_vals[i] < woe_vals[i+1]:
                    merge_idx = i
                    break
        if merge_idx == -1:
            break
        merged = {
            'min': df_valid_bins.iloc[merge_idx]['min'],
            'max': df_valid_bins.iloc[merge_idx+1]['max'],
            'goods': df_valid_bins.iloc[merge_idx]['goods'] + df_valid_bins.iloc[merge_idx+1]['goods'],
            'bads': df_valid_bins.iloc[merge_idx]['bads'] + df_valid_bins.iloc[merge_idx+1]['bads'],
            'total': df_valid_bins.iloc[merge_idx]['total'] + df_valid_bins.iloc[merge_idx+1]['total']
        }
        df_valid_bins = pd.concat([df_valid_bins.iloc[:merge_idx],
                                   pd.DataFrame([merged]),
                                   df_valid_bins.iloc[merge_idx+2:]], ignore_index=True)
        df_valid_bins = compute_metrics(df_valid_bins.to_dict('records'))
        if len(df_valid_bins) < 2:
            raise ValueError("单调性合并后箱数不足2，请调整初始分箱参数")

    # 有效分箱的 min / max 保持原始数值（包括 -inf / inf）
    # ---------- 6. 处理缺失箱 ----------
    missing_stats = []
    if special_mask.any():
        special_goods = (df.loc[special_mask, target] == good).sum()
        special_bads = (df.loc[special_mask, target] == bad).sum()
        special_total = special_mask.sum()
        good_prop = special_goods / total_good if total_good > 0 else 0
        bad_prop = special_bads / total_bad if total_bad > 0 else 0
        bad_rate = special_bads / special_total if special_total > 0 else 0
        eps = 1e-10
        good_prop = max(good_prop, eps)
        bad_prop = max(bad_prop, eps)
        woe = np.log(bad_prop / good_prop)
        iv = (bad_prop - good_prop) * woe
        ks = abs(bad_prop - good_prop)
        lift = bad_rate / overall_bad_rate if overall_bad_rate > 0 else np.inf
        missing_stats.append({
            'min': "MISSING_VALUE",
            'max': "MISSING_VALUE",
            'goods': special_goods,
            'bads': special_bads,
            'total': special_total,
            'good_prop': good_prop,
            'bad_prop': bad_prop,
            'bad_rate': bad_rate,
            'woe': woe,
            'iv': iv,
            'ks': ks,
            'lift': lift
        })
    df_missing = pd.DataFrame(missing_stats)

    # ---------- 7. 合并有效箱与缺失箱 ----------
    result = pd.concat([ df_missing, df_valid_bins], ignore_index=True)
    cols = ['min', 'max', 'goods', 'bads', 'total', 'good_prop', 'bad_prop', 'bad_rate', 'woe', 'iv', 'ks', 'lift']
    result = result[cols]
    return result




def calculate_all_ks(df, y_col='Y', exclude_cols=None, min_samples=50, plot_top_n=5, verbose=True, feature_cols=[]):
    """
    计算DataFrame中所有变量对目标Y的KS值
    
    参数:
    df: pandas DataFrame，包含特征变量和目标变量
    y_col: str，目标变量列名（1表示坏客户，0表示好客户）
    exclude_cols: list，需要排除的列名列表（如ID列等）
    min_samples: int，计算KS所需的最小样本量
    plot_top_n: int，绘制KS曲线的前N个变量
    verbose: bool，是否打印详细信息
    
    返回:
    ks_results: DataFrame，包含每个变量的KS值、p值等信息
    """
    start_time = time.time()
    
    # 确保目标变量存在
    if y_col not in df.columns:
        raise ValueError(f"目标变量 '{y_col}' 不在DataFrame的列中")
    
    # 确定需要计算KS的变量列表
    if exclude_cols is None:
        exclude_cols = []
    exclude_cols = list(set(exclude_cols + [y_col]))
    
    # 获取所有需要计算KS的变量 
    
    if verbose:
        print(f"开始计算{len(feature_cols)}个变量的KS值...")
        print(f"目标变量: {y_col}")
        print(f"排除变量: {exclude_cols}")
    
    # 存储结果
    ks_results = []
    
    # 分离好客户和坏客户
    good = df[df[y_col] == 0]
    bad = df[df[y_col] == 1]
    
    total_good = len(good)
    total_bad = len(bad)
    
    if verbose:
        print(f"样本总数: {len(df)}")
        print(f"好客户数量: {total_good} ({total_good/len(df):.2%})")
        print(f"坏客户数量: {total_bad} ({total_bad/len(df):.2%})")
    
    # 检查是否有足够的样本
    if total_good < min_samples or total_bad < min_samples:
        raise ValueError(f"好客户或坏客户样本量不足({min_samples}个)，无法计算KS值")
     
    
    # 遍历每个变量计算KS
    for i, col in enumerate(feature_cols):
        try:
            # 检查变量是否为数值型
            if not np.issubdtype(df[col].dtype, np.number):
                if verbose:
                    print(f"跳过非数值变量: {col}")
                continue
            
            # 检查是否有足够的非缺失值
            valid_good = good[col].dropna()
            valid_bad = bad[col].dropna()
            
            if len(valid_good) < min_samples or len(valid_bad) < min_samples:
                if verbose:
                    print(f"变量 {col} 的好客户或坏客户样本量不足，跳过")
                continue
            
            # 计算KS值（使用scipy的ks_2samp）
            ks_stat, p_value = stats.ks_2samp(valid_bad, valid_good)
            
            # 另一种计算方式（手动计算，与风控常用方法一致）
            # 将数据按变量值排序
            df_sorted = df[[col, y_col]].dropna().sort_values(by=col, ascending=False)
            
            # 计算累积分布
            df_sorted['cum_count'] = range(1, len(df_sorted) + 1)
            df_sorted['cum_bad'] = df_sorted[y_col].cumsum()
            df_sorted['cum_good'] = df_sorted['cum_count'] - df_sorted[y_col]
            
            # 计算累积比例
            df_sorted['cum_pct_bad'] = df_sorted['cum_bad'] / total_bad
            df_sorted['cum_pct_good'] = df_sorted['cum_good'] / total_good
            
            # 计算KS值
            df_sorted['ks'] = np.abs(df_sorted['cum_pct_bad'] - df_sorted['cum_pct_good'])
            ks_manual = df_sorted['ks'].max()
            
            # 找到KS值对应的位置
            ks_point = df_sorted[df_sorted['ks'] == ks_manual].iloc[0]
            
            # 存储结果
            ks_results.append({
                'variable': col,
                'ks_scipy': ks_stat,
                'ks_manual': ks_manual,
                'p_value': p_value,
                'ks_threshold': ks_point[col],
                'bad_pct_at_ks': ks_point['cum_pct_bad'],
                'good_pct_at_ks': ks_point['cum_pct_good'],
                'sample_size': len(df_sorted),
                'missing_rate': 1 - len(df_sorted)/len(df)
            }) 
                
        except Exception as e:
            if verbose:
                print(f"计算变量 {col} 的KS值时出错: {str(e)}")
            continue
    
    # 转换为DataFrame并按KS值排序
    ks_df = pd.DataFrame(ks_results).sort_values(by='ks_manual', ascending=False)
     
    if verbose:
        print(f"\nKS值计算完成! 共处理 {len(feature_cols)} 个变量，成功计算 {len(ks_df)} 个变量的KS值")
        print(f"计算耗时: {time.time() - start_time:.2f} 秒")
        print(f"KS值范围: {ks_df['ks_manual'].min():.4f} - {ks_df['ks_manual'].max():.4f}")
        print(f"平均KS值: {ks_df['ks_manual'].mean():.4f}")
    
    return ks_df
