import os
import pandas as pd


def to_excel_func(df, type_name, data_save_path, feature_part_name):
    if not os.path.exists(data_save_path):
        os.makedirs(data_save_path) 
    df.to_excel(f'{data_save_path}/{feature_part_name}_{type_name}.xlsx', index=False)


def to_csv_func(df, type_name, data_save_path, feature_part_name):
    if not os.path.exists(data_save_path):
        os.makedirs(data_save_path) 
    df.to_csv(f'{data_save_path}/{feature_part_name}_{type_name}.csv', index=False)