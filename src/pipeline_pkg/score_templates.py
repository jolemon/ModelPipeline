"""
SQL模板定义

存放 Lgb2Sql 使用的SQL模板字符串，与解析逻辑分离，
便于独立维护和修改SQL格式。
"""

# 完整版评分SQL模板（含空值填充、全空打标、评分卡映射）
SQL_FULL = '''
    DROP TABLE IF EXISTS {4};
    CREATE TABLE IF NOT EXISTS {4} AS 
    SELECT {0}
         , {12}
    FROM {11}
    ;

    DROP TABLE IF EXISTS {5};
    CREATE TABLE IF NOT EXISTS {5} AS  
    SELECT {0}, 
           1 / (1 + exp(-(({1})+({2})))) AS lgb2sql_score, 
           CASE WHEN LEAST({10}) = -999999 AND GREATEST({10}) = -999999 THEN 1 ELSE 0 END AS all_null_flag
    FROM (
        SELECT {0}, 
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
