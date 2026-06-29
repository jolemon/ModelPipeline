#!/bin/bash

import os 

##################### 常规配置 ##################################
output_dir = '/srv/output'
data_warehouse_dir = '/srv/data_warehouse'

dataset_file_name = 'dataset.csv'
feature_info_postfix = '_最终特征.xlsx'
feature_warehouse_file_name = '特征映射表.xlsx'
feature_warehouse_file_name_newbase = '特征映射表_新底座.xlsx'

filter_df_postfix = '_filter_df.csv'

part_id = 'loan_month'
sample_date = 'encash_date'

dataflag = 'data_flag'
dataflag_train, dataflag_test, dataflag_oot = 'train', 'test', 'oot'
train_split_size = 0.8

lgb_feature_importance_file_name = 'lgb_feature_importance.csv'
lgb_top10_feature_woe_bins_file_name = 'lgb_top10_feature_woe_bins.csv'
###################### 模型特定配置 ####################################
# product_name = 'XCJQH'

# target = 'target_mob6_30'
# pt_target = 'y_label'   # 压力测试y标
# train_start_part_id, oot_start_part_id, ptest_start_part_id = '202408', '202501', '202503'  

# feature_group_list = [
#     'br_zzx_part1' ,
#     'pboc_part1','pboc_part2', 'pboc_part3','pboc_part4', 'pboc_part5', 'pboc_part6','pboc_part7', 'pboc_part8', 'pboc_part9',
#     'bh_part1', 'bh_part2'
# ]
# pkl_model_name = 'xxmodel.pkl'

##################### 补充常规配置 #####################################
# data_dir = os.path.join(output_dir, product_name, 'feature') 
# model_dir = os.path.join(output_dir, product_name, 'model')   
# dataset_dir = os.path.join(output_dir, product_name, 'dataset')  
# dataset_path = os.path.join(dataset_dir, 'dataset.csv')

# lgb_params_log_file_name = f'{product_name}_lgb_params_log.csv'
# lgb_params_log_file_path = os.path.join(model_dir, lgb_params_log_file_name)

# pkl_model_path = os.path.join(model_dir, pkl_model_name)
# lgb_feature_importance_file_path = os.path.join(model_dir, lgb_feature_importance_file_name)
# lgb_top10_feature_woe_bins_path = os.path.join(model_dir, lgb_top10_feature_woe_bins_file_name)
feature_warehouse_path = os.path.join(data_warehouse_dir, feature_warehouse_file_name)
 
