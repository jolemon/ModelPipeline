#!/usr/bin/env python
# ! -*- coding: utf-8 -*-

'''
@File: lgb2sql.py
@Author: RyanZheng
@Email: ryan.zhengrp@gmail.com
@Created Time on: 2023-07-14

#1.0000000180025095e-35
'''
import codecs
import logging
import pandas as pd
import lightgbm


class Lgb2Sql:
    """LightGBM模型转Hive SQL生成器

    生成完整版打分SQL（含空值填充、全空打标、评分卡映射）。
    """
    sql_str = '''
        DROP TABLE IF EXISTS {4};
        CREATE TABLE IF NOT EXISTS {4} AS 
        SELECT {13}
             , {12}
        FROM {11}
        ;

        DROP TABLE IF EXISTS {5};
        CREATE TABLE IF NOT EXISTS {5} AS  
        SELECT {14}, 
               1 / (1 + exp(-(({1})+({2})))) AS lgb2sql_score, 
               CASE WHEN LEAST({10}) = -999999 AND GREATEST({10}) = -999999 THEN 1 ELSE 0 END AS all_null_flag
        FROM (
            SELECT {13}, 
                   {10},
                   {3}
            FROM {4}
        ) t
        ;


        DROP TABLE IF EXISTS {6};
        CREATE TABLE IF NOT EXISTS {6} AS 
        SELECT 
            *, 
            round(CASE 
                    WHEN all_null_flag = 1 OR CAST(lgb2sql_score AS FLOAT) <= 0 OR CAST(lgb2sql_score AS FLOAT) >= 1 THEN -999999
                  ELSE {7} - {8} * ln(CAST(lgb2sql_score AS FLOAT) / (1 - CAST(lgb2sql_score AS FLOAT)))
                  END, {9}) AS score_card
        FROM {5}
        ;
        '''

    feature_names = []

    def _build_tree_expressions(self, trees, sql_is_format=True, round_decimal=-1):
        """
        构建所有树的SQL表达式列表和列名列表

        遍历每棵树，递归构建CASE WHEN表达式，生成树得分列名。

        Args:
            trees: tree_info列表
            sql_is_format: 是否格式化SQL
            round_decimal: 小数位精度

        Returns:
            (trees_func_code_l, columns_l) 元组
        """
        trees_func_code_l = []
        columns_l = []

        for i, tree in enumerate(trees):
            one_tree_code = self.build_tree_sql(
                tree['tree_structure'], 1, sql_is_format, round_decimal
            )
            col_name = f'tree_{i}_score'
            columns_l.append(col_name)

            if i == len(trees) - 1:
                trees_func_code_l.append(
                    f'{one_tree_code}\n\t\tas {col_name}'
                )
            else:
                trees_func_code_l.append(
                    f'{one_tree_code}\n\t\tas {col_name},\n'
                )

        return trees_func_code_l, columns_l

    def generate_full_score_sql(self, lgb_model, keep_columns=['key'], sql_is_format=True, round_decimal=-1,
                 work_no='01011939', model_id='myjbv1_zy', table_date='20260122',
                 scorecard_shift=533.903595, scorecard_slope=72.134752, scorecard_round=2,
                 input_table=None, extra_columns=None, output_variables=False,
                 sort_by_importance=True, top_n=0):
        """
        生成完整打分SQL（支持Booster和LGBMClassifier两种输入）

        生成四段SQL：
        1. 空值填充表（NVL处理）
        2. 模型打分表（sigmoid + 全空打标）
        3. 评分卡映射表（log-odds转换）

        Args:
            lgb_model: lightgbm.Booster 或 LGBMClassifier 模型对象
            keep_columns: 保留列（主键等），默认 ['key']
            sql_is_format: 是否格式化SQL，默认 True
            round_decimal: 小数位精度，默认 -1 表示不四舍五入
            work_no: 工作编号，默认 '01011939'
            model_id: 模型ID，默认 'myjbv1_zy'
            table_date: 日期字符串，默认 '20260122'
            scorecard_shift: 评分卡偏移量，默认 533.903595
            scorecard_slope: 评分卡斜率，默认 72.134752
            scorecard_round: 评分卡小数位，默认 2
            input_table: 输入变量表名（可选，默认自动生成）
            extra_columns: 额外的样本字段列表（可选）
            output_variables: 是否在输出中包含模型变量字段，默认 False
            sort_by_importance: 变量字段是否按重要度排序，默认 True
            top_n: 变量字段输出数量限制，0 表示全部，默认 0

        Returns:
            str: 完整Hive SQL语句（含空值填充、全空打标、模型打分、评分卡映射）
        """

        json_object = self.dump_model(lgb_model)
        self.feature_names = json_object['feature_names']
        trees = json_object['tree_info']

        # 统一处理Booster和LGBMClassifier
        if isinstance(lgb_model, lightgbm.Booster):
            booster = lgb_model
            importances = booster.feature_importance(importance_type='gain')
        else:
            # sklearn API (LGBMClassifier / LGBMRegressor)
            importances = lgb_model.feature_importances_
            booster = lgb_model.booster_

        feature_name = booster.feature_name()

        # 创建DataFrame展示所有特征，筛选有效特征(Importance > 0)
        all_features = pd.DataFrame({
            'Feature': feature_name,
            'Importance': importances
        })
        positive_feats = all_features[all_features['Importance'] > 0]['Feature'].tolist()

        # logit = self.get_model_config(lgb_model)
        logit = -0.0

        trees_func_code_l, columns_l = self._build_tree_expressions(
            trees, sql_is_format, round_decimal
        )

        # 临时表命名（支持外部指定输入表）
        table_var = input_table or f'tmp_{work_no}_{table_date}_{model_id}_var'
        table_var_fillna = f'tmp_{work_no}_{table_date}_{model_id}_var_fillna'
        table_model_score = f'tmp_{work_no}_{table_date}_{model_id}_model_score'
        table_model_scorecard = f'tmp_{work_no}_{table_date}_{model_id}_model_scorecard'

        columns = ' + '.join(columns_l)
        trees_func_code = ''.join(trees_func_code_l)

        print(f'use_columns length: {len(positive_feats)}')
        use_columns_str = ','.join(positive_feats)
        fillna_columns_str = ','.join([f'NVL({feat}, -999999) AS {feat}' for feat in positive_feats])

        # 构建 inner columns（keep_columns + extra_columns）
        inner_columns = list(keep_columns)
        if extra_columns:
            for col in extra_columns:
                if col not in inner_columns:
                    inner_columns.append(col)
        inner_columns_str = ', '.join(inner_columns)

        # 计算按重要度排序的变量字段
        sorted_features = None
        if output_variables:
            sorted_df = all_features[all_features['Importance'] > 0]
            if sort_by_importance:
                sorted_df = sorted_df.sort_values('Importance', ascending=False)
            sorted_features = sorted_df['Feature'].tolist()
            if top_n > 0:
                sorted_features = sorted_features[:top_n]

        # 构建 outer columns（inner_columns + variable_columns，去重）
        outer_columns = list(inner_columns)
        if sorted_features:
            inner_columns_set = set(inner_columns)
            for feat in sorted_features:
                if feat not in inner_columns_set:
                    outer_columns.append(feat)
        outer_columns_str = ', '.join(outer_columns)

        score_sql = self.sql_str.format(','.join(keep_columns), columns, logit, trees_func_code, 
                               table_var_fillna, table_model_score, table_model_scorecard, scorecard_shift, 
                               scorecard_slope, scorecard_round, use_columns_str,
                               table_var, fillna_columns_str, inner_columns_str, outer_columns_str)
        return score_sql


    def dump_model(self, lgb_model):
        """
        获取模型dump信息（支持Booster和LGBMClassifier）

        Args:
            lgb_model: lightgbm.Booster 或 LGBMClassifier 模型

        Returns:
            模型dump后的字典
        """
        if isinstance(lgb_model, lightgbm.Booster):
            return lgb_model.dump_model()
        elif isinstance(lgb_model, lightgbm.LGBMClassifier):
            return lgb_model._Booster.dump_model()
        else:
            # 尝试获取booster_属性（sklearn API通用）
            if hasattr(lgb_model, '_Booster'):
                return lgb_model._Booster.dump_model()
            elif hasattr(lgb_model, 'booster_'):
                return lgb_model.booster_.dump_model()
            else:
                raise ValueError(f"不支持的模型类型: {type(lgb_model)}")

    def build_tree_sql(self, node, n, sql_is_format=True, round_decimal=-1):
        """
        递归构建单棵树的SQL表达式

        遍历树结构，根据分裂节点的特征和阈值生成嵌套的 CASE WHEN 表达式。
        对于叶子节点，直接返回叶子值；对于内部节点，递归构建左右子树。

        Args:
            node: 树结构节点（字典，包含 split_feature, threshold, left_child, right_child 等）
            n: 当前层级（用于缩进控制）
            sql_is_format: 是否格式化SQL（添加缩进和换行）
            round_decimal: 小数位精度，-1表示不四舍五入

        Returns:
            str: 树对应的SQL CASE WHEN 表达式字符串
        """
        n += 1
        if 'leaf_index' in node:
            leaf_value = round(node['leaf_value'], round_decimal) if round_decimal != -1 else node['leaf_value']
            if node['leaf_value'] != leaf_value:
                logging.debug(f"leaf_value: {node['leaf_value']}|{leaf_value} is different!")
                if node['leaf_value'] < 0:
                    leaf_value = -0.0000000000001
                else:
                    leaf_value = 0.0000000000001

            return '\t' * n + str(leaf_value) if sql_is_format else leaf_value

        condition = []
        split_feature = self.feature_names[node['split_feature']]
        is_default_left = node['default_left']

        if node['decision_type'] == '<=' or node['decision_type'] == 'no_greater':
            threshold = round(node['threshold'], round_decimal) if round_decimal != -1 else node['threshold']

            if 'e' in str(threshold):
                threshold = format(threshold, 'f')

            if node['threshold'] != threshold:
                logging.debug(f"threshold: {node['threshold']}|{threshold} is different!")
                if node['threshold'] < 0:
                    threshold = '-0.0000000000001'
                else:
                    threshold = '0.0000000000001'
            
            condition.append(
                f'{split_feature} is null and {str(is_default_left).lower()}==true or {split_feature}<={threshold}')
        else:
            threshold = round(node['threshold'], round_decimal) if round_decimal != -1 else node['threshold']
            
            if 'e' in str(threshold):
                threshold = format(threshold, 'f')

            if node['threshold'] != threshold:
                logging.debug(f"threshold: {node['threshold']}|{threshold} is different!")
                if node['threshold'] < 0:
                    threshold = '-0.0000000000001'
                else:
                    threshold = '0.0000000000001'
            
            condition.append(
                f'{split_feature} is null and {str(is_default_left).lower()}==false or {split_feature}=={threshold}')


        left = self.build_tree_sql(node['left_child'], n, sql_is_format, round_decimal)
        right = self.build_tree_sql(node['right_child'], n, sql_is_format, round_decimal)

        if sql_is_format:
            strformat = '\t' * n
            return f'{strformat}CASE WHEN ({condition[0]}) THEN\n{left}\n{strformat}ELSE\n{right}\n{strformat}END'
        else:
            return f'CASE WHEN ({condition[0]}) THEN {left} ELSE {right} END'

    def save_sql(self, filename='lgb_model.sql'):
        """
        保存SQL到文件

        Args:
            filename: SQL语句保存的文件路径

        Returns:
            None
        """
        with codecs.open(filename, 'w', encoding='utf-8') as f:
            f.write(self.sql_str)

