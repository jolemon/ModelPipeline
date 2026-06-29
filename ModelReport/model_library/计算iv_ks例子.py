feature_warehouse = get_data_warehouse(new_base=True) 
lower_order_var = [x.lower() for x in order_var] 
feature_info_df = feature_warehouse[feature_warehouse['字段名'].isin(lower_order_var)]

# 来源表
for c in lower_order_var: 
    row_str = ' | '.join(feature_info_df.loc[feature_info_df['字段名']==c, '来源表'].astype(str)) 
    if row_str=='nan':
        row_str = ' | '.join(feature_info_df.loc[feature_info_df['字段名']==c, '字段名'].astype(str)) 
    print(row_str) 

# 变量名
for c in lower_order_var: 
    if c not in feature_info_df['字段名'].tolist():
        c = '' # c.strip()
        print(f'{c}', end = '')
    row_str = ' | '.join(feature_info_df.loc[feature_info_df['字段名']==c, '字段含义'].astype(str)).strip()
    print(row_str) 


# 计算缺失率
# 定义数据表中的ID列，y标列，剔除列，特征列
id_columns = ['dubil_num', 'cert_no', 'cert_num', 'cust_id']
label_columns = [target] #, 'target_mob5_30', 'target_mob4_30', 'target_mob3_30'] 
remove_columns = ['cert_no', 'certno', 'encash_date', 'ci_rpt_id','createtime', 'part_id','reportno', 'reporttime', 'updatetime',
                  'max_ovds_mob6', 'max_ovds_mob5', 'max_ovds_mob4', 'max_ovds_mob3', 'max_ovds_mob2', 'max_ovds_mob1',  
                  'target_mob2_30', 'target_fpd30',
                  'rn', 'rnk', 'rw', 'rx', 'var_br_qrydate','var_brf_qrydate','var_zzx_qrydate',
                  'id', 'cust_id', 'part_id', 'data_dt',  'req_msg_id', 'req_reserve',  
                   'res_ext_info', 'insert_date', 'version', 'etl_tm',
                   'prd_name', 'prd_big_cls_cd', 'name', 'idcard', 'phone',
                  'jdapplyno', 'cert_no', 'part_id', 'tiaoe_date', 'mob1_7', 'mob2_15', 'mob3_30', 'mob4_30', 'mob5_30', 'mob6_30', 
                      'pboc_bs61_141', 'prd_sub_cls_cd', 'repay_mode', 'totl_prod_cnt', 'loan_data_dt', 'obs_data_dt', 'mpd_days', 'mob', 'h_max_ovd_days', 'cur_ovd_days', 'rk',  
                      'dubil_num', 'cert_no', 'loan_dt', 'cert_num', 'cust_id', 'data_dt',   'data_flag', 'flag_good', 'flag_bad', 'flag_grey' , 
                 ] 


def handle_feature_missing_rate2(df): 
    all_columns = set(df.columns)
    feature_columns = [x for x in all_columns if x not in id_columns and x not in label_columns and x not in remove_columns]
    
    # 筛选 object 类型的列
    object_cols = df.select_dtypes(include=['object']).columns 
    # 转换为 category 类型
    cate_cols = [col for col in object_cols if col in feature_columns]
    df[cate_cols] = df[cate_cols].astype('category')  
    
    feature_columns = sorted(feature_columns)  
    
    overall_distribution = calc_missing(df, feature_columns)  
    return overall_distribution

#导入数据
dataset=pd.read_csv('/srv/output/MYJBV1_ZY_ALL/dataset/final_dataset.csv')
dataset

df = dataset[['part_id'] + order_var].copy()
 
# 将小于-9999的值替换为NaN
for col in order_var:
    if pd.api.types.is_numeric_dtype(df[col]):
        df.loc[df[col] <= -99999, col] = np.nan
 
df_train = df[df['part_id'].isin([202503,202504,202405])][order_var]
df_oot = df[df['part_id'].isin([202506,202507])][order_var]
df_train

overall_distribution = handle_feature_missing_rate2(df_train)
for c in order_var: 
    row_str = ' | '.join(overall_distribution.loc[overall_distribution['index']==c, 'missing'].astype(str)) 
    print(row_str) 

overall_distribution = handle_feature_missing_rate2(df_oot)
for c in order_var:
    row_str = ' | '.join(overall_distribution.loc[overall_distribution['index']==c, 'missing'].astype(str)) 
    print(row_str) 

## 计算train/oot的IV 
df = report_input.copy()
object_cols = df.select_dtypes(include=['object']).columns    # 筛选 object 类型的列
cate_cols = [col for col in object_cols if col in order_var]   # 转换为 category 类型
df[cate_cols] = df[cate_cols].astype('category') 
df_train = df[df['part_id'].isin([202503,202504,202405])][order_var+[target]]
df_oot = df[df['part_id'].isin([202506,202507])][order_var+[target]]
iv_train = calc_iv(df_train, order_var, label=target)  
iv_train
for c in order_var:
    row_str = ' | '.join(iv_train.loc[iv_train['index']==c, 'iv'].astype(str)) 
    print(row_str) 

iv_oot = calc_iv(df_oot, order_var, label=target)  
for c in order_var:
    row_str = ' | '.join(iv_oot.loc[iv_oot['index']==c, 'iv'].astype(str)) 
    print(row_str) 

##  计算train/oot的KS
 
# 计算所有变量的KS值
ks_results = calculate_all_ks(df_train, y_col=target, exclude_cols=[ target, 'cert_num', 'cust_id', 'data_dt', 'part_id', 'data_flag', 'probability(0)',
       'probability(1)', 'ALL_score'], feature_cols=order_var)
for c in order_var:
    row_str = ' | '.join(ks_results.loc[ks_results['variable']==c, 'ks_scipy'].astype(str)) 
    print(row_str)  
 
# 计算所有变量的KS值
ks_results = calculate_all_ks(df_oot, y_col=target, exclude_cols=['cert_num', 'cust_id', 'data_dt', 'part_id', 'data_flag', 'probability(0)',
       'probability(1)', 'ALL_score'], feature_cols=order_var)
for c in order_var:
    row_str = ' | '.join(ks_results.loc[ks_results['variable']==c, 'ks_scipy'].astype(str)) 
    print(row_str)