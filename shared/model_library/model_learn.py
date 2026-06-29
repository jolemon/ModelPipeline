import pandas as pd
import os 
import datasources
import datetime
import optuna
import math
from optuna.integration import LightGBMPruningCallback
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn2pmml import PMMLPipeline, sklearn2pmml 
from sklearn.model_selection import StratifiedKFold,KFold
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import FunctionTransformer

import numpy as np
import lightgbm as lgb
from sklearn.metrics import accuracy_score 
from sklearn.metrics import roc_auc_score
from sklearn.metrics import confusion_matrix
from sklearn.metrics import roc_curve,auc


def model_metrics_v4(y, y_prob, pos_label=1, sample_weight=None):
    """ 评估 """
    fpr, tpr, _ = roc_curve(y, y_prob, pos_label=pos_label, sample_weight=sample_weight)
    auc_res = auc(fpr, tpr) 
    metrics = {
        'AUC': auc_res, 
        'KS': max(tpr-fpr)
    }  
    
    return metrics


def calc_auc_ks_by_month(df, target='target_mob6_30', score_col='score', sample_date='encash_date', sample_weight_col=''):
    
    if len(df) < 2000000:
        tmp_df = df.copy()
    else:
        tmp_df = df  
    tmp_df['loan_month'] = tmp_df[sample_date].astype(str).apply(lambda x: x.replace('-', '')[0:6])
    tmp_df['good_flag'] = tmp_df[target].apply(lambda x: int(1-x)) 
    #逐月评估
    m_list, count_list, good_list, bad_list, badrate_list, auc_list, ks_list, weighted_auc_list, weighted_ks_list = [], [], [], [], [], [], [], [], []
    for m in list(set(tmp_df['loan_month'].tolist())) + ['all']:
        if m != 'all':
            m_data = tmp_df[(tmp_df['loan_month'] == m)] 
        else:
            m_data = tmp_df

        metrics = model_metrics_v4(m_data['good_flag'], m_data[score_col])
        m_list.append(m)
        count_list.append(len(m_data))
        good_list.append(len(m_data) - sum(m_data[target]))
        bad_list.append(sum(m_data[target]))
        badrate_list.append(np.mean(m_data[target]))
        auc_list.append(metrics['AUC'])
        ks_list.append(metrics['KS'])
        
        m_weights = None
        if sample_weight_col: 
            # m_weights = calc_weight_for_oos(m_data, pos_ratio, mob6_amt_in_pos) 
            m_weights = m_data[sample_weight_col].astype(float) 
            amt_metrics = model_metrics_v4(m_data['good_flag'], m_data[score_col], sample_weight=m_weights)  
            weighted_auc_list.append(amt_metrics['AUC'])
            weighted_ks_list.append(amt_metrics['KS'])

    result = {'观察点月':m_list,'总':count_list,'好':good_list,'坏':bad_list,'坏样本率':badrate_list, 'KS':ks_list,'AUC':auc_list}
    
    if sample_weight_col: 
        result['金额KS'] = weighted_ks_list 
        result['金额AUC'] = weighted_auc_list 
    return pd.DataFrame(result).sort_values(by=['观察点月'], ascending=True)  
    

def detailed_val_report(Y,Y_score,bins_,bins_reverse_sort, gen_report=False):
    #生成分段评估报告
    base_data_df=pd.DataFrame({'seg':bins_,'score':Y_score,'label':Y}) 
    base_data_df['bins_right'] = base_data_df['seg'].apply(lambda x: x.right).astype(float)
    base_data_df['seg_1']=base_data_df['seg'].apply(lambda x:str(x))
    nrows = len(Y)
    vc_1=base_data_df['label'].value_counts().reset_index() 
    vc_1 = vc_1.sort_values(by=['label'],ascending=True) 
    bad = vc_1.iloc[1,1]# 计算逾期总人数
    good = vc_1.iloc[0,1]# 计算好人的总人数
    bad_cnt, good_cnt = 0, 0 # 累计坏人人数 ，累计好人的人数
    GROUP_CNT,GROUP_SEG=[],[]
    GROUP_MIN, GROUP_MAX = [], []
    GOOD_CNT,GOOD_PCTG,GOOD_PCTG_CUM = [],[],[]
    BAD_CNT,BAD_PCTG,BAD_PCTG_CUM = [],[],[]
    BADRATE_CUM = []
    BAD_RATE = []
    KS = []
    CUM_TOTAL_RATE=[] 
    unique_intervals = bins_.unique()
    # sorted_intervals = sorted(unique_intervals, key=lambda x: x.left,reverse=bins_reverse_sort) 
    sorted_intervals = sorted(unique_intervals, key=lambda x: (x.left if hasattr(x, 'left') else float('inf') if x != x else x)) 
    bins = [str(interval) for interval in sorted_intervals] # 转换为字符串列表
  
    dct_report = {}
    for b in bins: 
        ds = base_data_df[base_data_df['seg_1']==b]
        if len(ds)==0:#跳过空区间
            continue 
        if len(ds['label'].value_counts().reset_index())>1:#处理分桶内可能没有坏样本的情况
            vc_2=ds['label'].value_counts().reset_index()
            vc_2 = vc_2.sort_values(by=['label'],ascending=True) 
            bad1 = vc_2.iloc[1,1]
            good1 = vc_2.iloc[0,1]
        else:
            bad1 = 0
            good1 = ds['label'].value_counts().reset_index().iloc[0,1]
        group_cnt=(bad1+good1) 
        group_seg=b
        group_min, group_max = b.split(',')[0].strip('(').strip(), b.split(',')[1].strip(']').strip()
        bad_cnt += bad1
        good_cnt += good1
        bad_pctg=round(bad1/bad,4)
        good_pctg=round(good1/good,4)
        bad_pctg_cum = round(bad_cnt/bad,4) # 一箱一箱累加 到这一箱一共有多少逾期 占所有逾期的比例
        good_pctg_cum = round(good_cnt/good,4)
        badrate = round(bad1/(bad1+good1),4) 
        cum_badrate = round(bad_cnt/(bad_cnt+good_cnt),4)  
        seg_total=round((bad1+good1)/(bad_cnt+good_cnt),3)
        cum_total=round((bad_cnt+good_cnt)/(bad+good),3)
        ks = round(math.fabs((bad_cnt / bad) - (good_cnt / good)),4) # 计算KS值
        GROUP_CNT.append(group_cnt)
        GROUP_SEG.append(group_seg)
        GROUP_MIN.append(group_min)
        GROUP_MAX.append(group_max)
        BAD_CNT.append(bad1)
        GOOD_CNT.append(good1)
        BAD_PCTG.append(bad_pctg)
        GOOD_PCTG.append(good_pctg)
        BAD_PCTG_CUM.append(bad_pctg_cum)
        GOOD_PCTG_CUM.append(good_pctg_cum)
        BAD_RATE.append(badrate)
        CUM_TOTAL_RATE.append(cum_total)
        BADRATE_CUM.append(cum_badrate)
        KS.append(ks)
        dct_report['分段'] = GROUP_SEG
        dct_report['min'] = GROUP_MIN
        dct_report['max'] = GROUP_MAX
        dct_report['分段数'] = GROUP_CNT
        dct_report['好样本数'] = GOOD_CNT
        dct_report['好样本占比'] = GOOD_PCTG
        dct_report['好样本累计占比'] = GOOD_PCTG_CUM
        dct_report['坏样本数'] = BAD_CNT
        dct_report['坏样本占比'] = BAD_PCTG
        dct_report['坏样本累计占比'] = BAD_PCTG_CUM
        dct_report['坏样本率'] = BAD_RATE
        dct_report['总数累计占比'] = CUM_TOTAL_RATE
        dct_report['KS'] = KS
        dct_report['累计坏样本率'] = BADRATE_CUM
        
    val_report = pd.DataFrame(dct_report)  
    #新增一行0用于复制gini的计算
    val_report_help1=pd.DataFrame([0,0,0,0,0,0,0,0,0,0,0,0,0,0]).T
    val_report_help1.columns=val_report.columns
    val_report=pd.concat([val_report_help1,val_report],ignore_index=True) 
    val_report_help2=val_report.iloc[0:-1,[-8,-5]].rename(columns={'好样本累计占比':'GOOD_PCTG_CUM_help',
                                                            '坏样本累计占比':'BAD_PCTG_CUM_help'})
    val_report_help3=pd.DataFrame([0,0]).T
    val_report_help3.columns=val_report_help2.columns
    val_report_help2=pd.concat([val_report_help3,val_report_help2],ignore_index=True)
    val_report=pd.concat([val_report,val_report_help2],axis=1)
    val_report['auc_help']=val_report.apply(lambda x:(x['好样本累计占比']-x['GOOD_PCTG_CUM_help'])
                                        *(x['坏样本累计占比']+x['BAD_PCTG_CUM_help'])*0.5,axis=1)
    val_report['gini_help']=val_report.apply(lambda x:(x['坏样本累计占比']-x['BAD_PCTG_CUM_help'])
                                        *(x['好样本累计占比']+x['GOOD_PCTG_CUM_help'])*0.5,axis=1)
    KS=max(val_report['KS'])
    AUC=round(sum(val_report['auc_help']),4)
    GINI=round(abs(2*(0.5-sum(val_report['gini_help']))),4)
    val_report['lift']=val_report.apply(lambda x:round(0 if x['坏样本率']==0 else x['坏样本率']/(val_report['坏样本数'].sum()/val_report['分段数'].sum()),1),axis=1)
    val_report['cum_lift']=val_report.apply(lambda x:round(0 if x['累计坏样本率']==0 else x['累计坏样本率']/(val_report['坏样本数'].sum()/val_report['分段数'].sum()),1),axis=1)
    val_report['odds']=val_report.apply(lambda x:round(0 if x['坏样本数']==0 else x['好样本数']/x['坏样本数'],1),axis=1)
    val_report['分段总数占比']=val_report.apply(lambda x:round(x['分段数']/val_report['分段数'].sum(),3),axis=1)
    val_report.loc['col_sum']=val_report.iloc[:,3:].apply(lambda x: x.sum(),axis=0)
    val_report.loc['col_sum','坏样本率']=val_report['坏样本数'].sum()/val_report['分段数'].sum()
    val_report.loc['col_sum','KS']=KS
    val_report.loc['col_sum','auc_help']=AUC
    val_report.loc['col_sum','gini_help']=GINI
    if gen_report: 
        show_cols = ['分段', 'min', 'max', '坏样本数', '好样本数', '分段数', '坏样本率', '累计坏样本率', '坏样本累计占比', 'KS', 'lift', 'cum_lift']
        res = val_report.query('max != 0 and max == max')[show_cols]
        return KS,GINI,AUC,res
    return KS,GINI,AUC,val_report


def risk_division_report(Y, Y_score, bins, bins_reverse_sort):
    #生成风险分档评估报告
    KS,GINI,AUC,val_report = detailed_val_report(Y,Y_score,bins,bins_reverse_sort,gen_report=True)
    val_report['分段总数占比']=val_report.apply(lambda x:round(x['分段数']/(val_report['分段数'].sum()),3),axis=1)
    val_report['lift']=val_report.apply(lambda x:round(0 if x['坏样本率']==0 else x['坏样本率']/(val_report['坏样本数'].sum()/val_report['分段数'].sum()),1),axis=1)
    return val_report[['分段', '分段数', '坏样本数', '坏样本率', '分段总数占比', 'lift']]


def bins_func(bins_series):
    cleaned_bins = bins_series[bins_series != 'missing']
    
    # 将'inf'字符串转换为float('inf')
    def convert_inf(x):
        if x == 'inf':
            return float('inf')
        elif x == '-inf':
            return -float('inf')
        else:
            return float(x)
    
    # 应用转换函数
    numeric_bins = cleaned_bins.apply(convert_inf)
    
    # 确保单调递增
    sorted_bins = sorted(numeric_bins.unique())
    if sorted_bins[0] != -float('inf'):
        sorted_bins = [-float('inf')] + sorted_bins  
    return pd.Series(sorted_bins)


def calculate_lift(df, y_col='y', score_col='score', 
                  percentiles=[10, 5, 2, 1], 
                  lower_is_riskier=True):
    """
    计算指定百分比的Lift值
    
    参数:
    df: DataFrame，包含y标签和模型预测分数
    y_col: str，y标签的列名，默认为'y'（1表示坏客户，0表示好客户）
    score_col: str，预测分数的列名，默认为'score'
    percentiles: list，要计算的百分比列表，默认为[10, 5, 2, 1]
    lower_is_riskier: bool，分数越低是否表示风险越高，默认为True
    
    返回:
    dict，包含各百分比对应的Lift值
    """
    # 确定排序方向：在风控中，通常分数越低表示风险越高
    ascending = lower_is_riskier
    
    # 按预测分数排序
    df_sorted = df.sort_values(by=score_col, ascending=ascending).reset_index(drop=True)
    
    # 计算总体坏客户率
    overall_bad_rate = df_sorted[y_col].mean()
    
    # 计算各百分比的Lift
    lift_results = {}
    for p in percentiles:
        # 计算要取的样本数量
        n = int(len(df_sorted) * p / 100)
        
        # 取风险最高的p%的样本（根据排序方向）
        top_p = df_sorted.iloc[:n]
        
        # 计算这部分样本中的坏客户率
        top_p_bad_rate = top_p[y_col].mean()
        
        # 计算Lift
        lift = top_p_bad_rate / overall_bad_rate
        
        # 保存结果
        lift_results[f"{p}%"] = f"{lift:.2f}"   # float(round(lift, 2))
    
    return lift_results


def calculate_lift_by_month(score_df, search_pt, percentiles=[10, 5, 2, 1], y_='mob6_30', part_id='apply_mth', SCORE='scorecard_score'): 
    res = [] 
    for pt in search_pt: 
        aaa = score_df[score_df[part_id] == pt]  
        aaa = aaa[aaa[y_]>=0]
        lift_values = calculate_lift(aaa, y_col=y_ , score_col=SCORE, percentiles=[10, 5, 2, 1], lower_is_riskier=True)
        # print(f"{pt} Lift Values:", lift_values)
        lift_values['观察点月'] = pt
        res.append(lift_values)
    aaa = score_df[score_df[part_id].isin(search_pt)] 
    aaa = aaa[aaa[y_]>=0]
    lift_values = calculate_lift(aaa, y_col=y_, score_col=SCORE, percentiles=[10, 5, 2, 1], lower_is_riskier=True)
    lift_values['观察点月'] = 'all'
    res.append(lift_values)
    res_df = pd.DataFrame(res)
    return res_df[['观察点月', '10%', '5%', '2%', '1%']]  #.style.format({'max': '{.2f}'})
 


def eval_ovd_amt_metrics(df, target_col, score_col, prin_bal_amount_col, loan_amount_col, q=100):
    # 确保好客户贷余为0
    df.loc[df[target_col] == 0, prin_bal_amount_col] = 0
    
    _, rebins = pd.qcut(df[score_col], q=q, retbins=True, duplicates='drop')
    df['bin'] = pd.cut(df[score_col], bins=rebins)
    bin_df = df.groupby('bin')[target_col].agg(['count','sum','mean'])
    bin_df = bin_df.reset_index()
    bin_df.columns = ['bin', 'cnt', 'bad_cnt', 'bad_rate']

    bin_df['total_pct'] = bin_df['cnt'] / bin_df['cnt'].sum()
    bin_df['bad_pct'] = bin_df['bad_cnt'] / bin_df['bad_cnt'].sum()
    # 支用金额
    bin_df['放款'] = df.groupby('bin')[loan_amount_col].sum().values
    bin_df['放款占比'] = bin_df['放款'] / bin_df['放款'].sum()
    # 逾期金额
    bin_df['ovd_amount'] = df.groupby('bin')[prin_bal_amount_col].sum().values
    bin_df['逾期金额占比*'] = bin_df['ovd_amount'] / bin_df['ovd_amount'].sum()
    bin_df['金额逾期率'] = bin_df['ovd_amount'] / bin_df['放款']
    # 累计占比
    bin_df['累计坏率'] = bin_df['bad_cnt'].cumsum()/bin_df['cnt'].cumsum()
    bin_df['累计金额逾期率'] = bin_df['ovd_amount'].cumsum()/bin_df['放款'].cumsum()
     
    # lift
    bin_df['坏率Lift'] = bin_df['bad_rate'] / df[target_col].mean()
    bin_df['累计坏率Lift'] = bin_df['累计坏率'] / df[target_col].mean()
    bin_df['金额逾期率Lift'] = bin_df['金额逾期率'] / (df[prin_bal_amount_col].sum()/df[loan_amount_col].sum())
    bin_df['累计金额逾期率Lift'] = bin_df['累计金额逾期率'] / (df[prin_bal_amount_col].sum()/df[loan_amount_col].sum())
    
    bin_df['累计逾期金额占比'] = bin_df['ovd_amount'].cumsum()/bin_df['ovd_amount'].sum()
    bin_df['累计逾期客户占比'] = bin_df['bad_cnt'].cumsum()/bin_df['bad_cnt'].sum()
    bin_df['坏率'] = bin_df['bad_rate']
    bin_df['逾期客户占比*'] = bin_df['bad_pct']
    
    # bin_df['累计逾期金额占比/累计逾期客户占比'] = bin_df['累计逾期金额占比']/bin_df['累计逾期客户占比']
    return bin_df[['bin', 'cnt', 'bad_cnt',  
                   '逾期客户占比*', '累计逾期客户占比',
       
       '坏率', '累计坏率', '坏率Lift', '累计坏率Lift',
                   '放款占比', '逾期金额占比*', '累计逾期金额占比', # '累计逾期金额占比/累计逾期客户占比',
       '金额逾期率', '累计金额逾期率', '金额逾期率Lift', '累计金额逾期率Lift'  ]]


def binning_cross_analysis(df, score_new_col='新分数', score_old_col='老分数', target_col='标签',
                           ovd_amt_col='逾期金额', encash_amt_col='放款金额', n_bins=10):
    """
    对新老分数进行等频分箱并交叉分析
    
    Parameters:
    -----------
    df : DataFrame
        包含新分数、老分数和标签列的数据集
    score_new_col : str
        新分数列名
    score_old_col : str
        老分数列名
    target_col : str
        标签列名（取值0/1）
    n_bins : int
        分箱数量
    
    Returns:
    --------
    result_df : DataFrame
        包含交叉分箱统计结果的DataFrame
    """
    
    # 创建数据副本，避免修改原数据
    data = df.copy()
    
    # 等频分箱 - 新分数
    data['新分数_bin'] = pd.qcut(data[score_new_col], q=n_bins, labels=False, duplicates='drop')
    # 等频分箱 - 老分数
    data['老分数_bin'] = pd.qcut(data[score_old_col], q=n_bins, labels=False, duplicates='drop')
   
    # 计算整体坏样本率
    total_bad = data[target_col].sum()
    total_bad_amt =  data[ovd_amt_col].sum()
    total_samples = len(data)
    total_encash_amt = data[encash_amt_col].sum()
    overall_bad_rate = total_bad / total_samples
    overall_amt_bad_rate = total_bad_amt/ total_encash_amt
    
    # 创建交叉分组统计
    cross_stats = data.groupby(['新分数_bin', '老分数_bin']).agg({
        target_col: ['count', 'sum'],
        encash_amt_col: ['sum'],
        ovd_amt_col: ['sum'],
    }).reset_index()
    
    # 重命名列
    cross_stats.columns = ['新分数_bin', '老分数_bin', '样本数', '坏样本数', '放款金额', '逾期金额']
    
    # 计算坏样本率
    cross_stats['坏样本率'] = cross_stats['坏样本数'] / cross_stats['样本数']
    cross_stats['金额逾期率'] = cross_stats['逾期金额'] / cross_stats['放款金额']
    
    # 计算lift
    cross_stats['lift'] = cross_stats['坏样本率'] / overall_bad_rate
    cross_stats['金额逾期率lift'] = cross_stats['金额逾期率'] / overall_amt_bad_rate
    
    # 添加分箱区间信息（可选）
    # 获取新分数的分箱边界
    new_bin_edges = pd.qcut(data[score_new_col], q=n_bins, retbins=True, duplicates='drop')[1]
    new_bin_labels = [f'({new_bin_edges[i]:.2f}, {new_bin_edges[i+1]:.2f}]' 
                      for i in range(len(new_bin_edges)-1)]
    
    # 获取老分数的分箱边界
    old_bin_edges = pd.qcut(data[score_old_col], q=n_bins, retbins=True, duplicates='drop')[1]
    old_bin_labels = [f'({old_bin_edges[i]:.2f}, {old_bin_edges[i+1]:.2f}]' 
                      for i in range(len(old_bin_edges)-1)]
    
    # 映射分箱区间
    cross_stats['新分数区间'] = cross_stats['新分数_bin'].map(
        dict(zip(range(len(new_bin_labels)), new_bin_labels)))
    cross_stats['老分数区间'] = cross_stats['老分数_bin'].map(
        dict(zip(range(len(old_bin_labels)), old_bin_labels)))
    
    # 按分箱排序
    cross_stats = cross_stats.sort_values(['新分数_bin', '老分数_bin'])
    
    # 选择并重排最终列
    result_df = cross_stats[[
        '新分数_bin', '新分数区间', '老分数_bin', '老分数区间', 
        '样本数', '坏样本数', '坏样本率', 'lift', '金额逾期率', '金额逾期率lift'
    ]]
    
    return result_df


def psi_report(df, target='mob6_30', SCORE='scorecard_score', bins=10):
    score_csv = df.copy()
    score_csv['score_cut']=pd.cut(score_csv[SCORE], bins, precision=0)  #等距分桶

    y_train_score=score_csv[(score_csv['data_flag']=='train')|(score_csv['data_flag']=='test')]  
    y_train_score_group=y_train_score.groupby(['score_cut'])[target].sum().reset_index()
    score_cut_data_train=pd.value_counts(y_train_score['score_cut']).sort_index().reset_index().rename(columns={'score_cut':'score_cut_count'}) 
    plot_data_train=pd.concat([y_train_score_group,score_cut_data_train],axis=1).rename(columns={'count':'score_cut_count_train', 'bad':'bad_sum_train', 'index':'index_train'})
    
    y_oot_score=score_csv[score_csv['data_flag']=='oot']
    y_oot_score_group=y_oot_score.groupby(['score_cut'])[target].sum().reset_index()
    score_cut_data_oot=pd.value_counts(y_oot_score['score_cut']).sort_index().reset_index().rename(columns={'score_cut':'score_cut_count'})
    plot_data_oot=pd.concat([y_oot_score_group,score_cut_data_oot],axis=1).rename(columns={'count':'score_cut_count_oot', 'bad':'bad_sum_oot', 'index':'index_oot'})
    
    psi_df=pd.concat([plot_data_train,plot_data_oot],axis=1)[['score_cut','score_cut_count_train','score_cut_count_oot']] 
    psi_df.columns = ['score_cut_1', 'score_cut', 'score_cut_count_train', 'score_cut_count_oot']
    psi_df['min'] = psi_df['score_cut'].apply(lambda x: int(float(str(x).split(',')[0].strip('('))))
    psi_df['max'] = psi_df['score_cut'].apply(lambda x: int(float(str(x).split(',')[1].strip(']').strip())))
    psi_df['train_pcnt']=psi_df['score_cut_count_train'].apply(lambda x: x*1.0/psi_df['score_cut_count_train'].sum())
    psi_df['oot_pcnt']=psi_df['score_cut_count_oot'].apply(lambda x:  x*1.0/psi_df['score_cut_count_oot'].sum())
    psi_df['pcnt_diff']=psi_df.apply(lambda x:x.oot_pcnt-x.train_pcnt,axis=1)
    psi_df['pcnt_weight']=psi_df.apply(lambda x:math.log((x.oot_pcnt+1e-10)/(x.train_pcnt+1e-10)),axis=1)
    psi_df['index']=psi_df['pcnt_diff']*psi_df['pcnt_weight']
    psi_df['score_cut']=psi_df['score_cut'].astype('object')
    psi_df['train_pcnt_str']=psi_df['train_pcnt'].apply(lambda x: '{:.2f}%'.format(x*100))
    psi_df['oot_pcnt_str']=psi_df['oot_pcnt'].apply(lambda x: '{:.2f}%'.format(x*100))
    print('PSI INDEX:',sum(psi_df['index']))
    psi_df=psi_df.iloc[:, 1:]
    reprot_excel_df = psi_df[[ 'min', 'max', 'score_cut_count_train', 'score_cut_count_oot', 'train_pcnt_str', 'oot_pcnt_str', 'index']]
    reprot_excel_df.columns = [ 'min', 'max', '开发样本数', '跨时间样本数', '开发样本占比', '跨时间验证样本占比', 'psi']
    return reprot_excel_df


def risk_classification(df, score_col='score', target_col='target', 
                                 risk_dict={'A': 0.30, 'B': 0.20, 'C': 0.40, 'D': 0.08, 'E': 0.02}):
    """
    客户风险分类表
    
    根据风险等级字典将客户按分数从高到低划分为不同风险等级，
    并生成各等级的统计报告。在 risk_division_report() 基础上实现。
    
    采用先等频分100箱、再按整箱合并的策略，确保同一分数不会被分到不同区间。
    参数:
    -----------
    df : DataFrame
        包含分数和标签的数据集，每一行代表一个用户
    score_col : str
        分数列名，默认为'score'
    target_col : str
        标签列名，默认为'target'（1表示坏客户，0表示好客户）
    risk_dict : dict
        风险等级字典，键为风险等级命名，值为该档风险的人数占比。
        字母'A'是分数最高的一档，从字母'A'到字母'E'，越往后分数越低。
    
    返回:
    --------
    result_df : DataFrame
        客户风险分类表，列为：风险等级、分段区间、分段数、占比、坏样本数、坏样本率
    """
    data = df[[score_col, target_col]].copy()
    n = len(data)
    
    risk_levels = list(risk_dict.keys())
    target_pcts = list(risk_dict.values())
    
    # 验证占比之和为1
    if abs(sum(target_pcts) - 1.0) > 1e-6:
        raise ValueError("risk_dict 中的占比之和必须等于1")
    
    # 先等频分100箱，确保同一分数不会被拆开
    data['bin'] = pd.qcut(data[score_col], q=100, labels=False, duplicates='drop')
    
    # 按分数降序排列各箱（高分在前）
    bin_info = data.groupby('bin').agg({
        score_col: ['min', 'max', 'count'],
        target_col: 'sum'
    }).reset_index()
    bin_info.columns = ['bin', 'bin_min', 'bin_max', 'cnt', 'bad']
    bin_info = bin_info.sort_values(by='bin_max', ascending=True).reset_index(drop=True)
    
    # 计算各档目标人数（四舍五入）
    target_counts = [int(round(pct * n)) for pct in target_pcts]
    diff = n - sum(target_counts)
    idx = len(target_counts) - 1
    while diff != 0:
        if diff > 0:
            target_counts[idx] += 1
            diff -= 1
        else:
            if target_counts[idx] > 0:
                target_counts[idx] -= 1
                diff += 1
        idx = (idx - 1) % len(target_counts)
    
    # 按整箱分配到各风险等级（从低分开始累加，达到目标就切换上一档）
    bin_to_level = {}
    current_level = len(risk_levels) - 1  # 从最低档E开始
    current_count = 0
    
    for _, row in bin_info.iterrows():
        bin_id = int(row['bin'])
        bin_cnt = int(row['cnt'])
        
        # 如果当前不是第一档，且当前档已达到或超过目标人数，则切换到上一档
        if current_level > 0 and current_count >= target_counts[current_level]:
            current_level -= 1
            current_count = 0
        
        bin_to_level[bin_id] = current_level
        current_count += bin_cnt
    
    # 为每个样本分配风险等级索引
    data['risk_level_idx'] = data['bin'].map(bin_to_level)
    
    # 计算每个等级的分数区间边界
    level_intervals = {}
    for level_idx in range(len(risk_levels)):
        level_data = data[data['risk_level_idx'] == level_idx]
        if len(level_data) > 0:
            level_intervals[level_idx] = {
                'min': level_data[score_col].min(),
                'max': level_data[score_col].max()
            }
    
    # 构造 bins 列（pd.Interval），用于调用 risk_division_report
    def make_interval(level_idx):
        if level_idx not in level_intervals:
            return pd.Interval(0, 0)
        min_s = level_intervals[level_idx]['min']
        max_s = level_intervals[level_idx]['max']
        if level_idx == 0:
            return pd.Interval(min_s, float('inf'), closed='neither')
        elif level_idx == len(risk_levels) - 1:
            return pd.Interval(-float('inf'), max_s, closed='right')
        else:
            return pd.Interval(min_s, max_s, closed='right')
    
    data['bins'] = data['risk_level_idx'].apply(make_interval)
    
    # 调用 risk_division_report 生成基础报告
    report = risk_division_report(data[target_col], data[score_col], data['bins'], bins_reverse_sort=True)
    
    # risk_division_report 内部按区间升序排序，最高分档在最后
    # 反转顺序，让A档在第一行
    report = report.iloc[::-1].reset_index(drop=True)
    
    # 格式化输出
    result = []
    for i, level in enumerate(risk_levels):
        if i >= len(report):
            break
        row = report.iloc[i]
        
        # 构造分段区间字符串（与示例输出格式保持一致）
        if i == 0:  # A档
            lower = int(level_intervals[i + 1]['max']) if (i + 1) in level_intervals else int(level_intervals[i]['min'])
            seg_str = f"({lower},  inf]"
        elif i == len(risk_levels) - 1:  # 最后一档
            upper = int(level_intervals[i]['max'])
            seg_str = f"(-inf, {upper}]"
        else:
            lower = int(level_intervals[i + 1]['max']) if (i + 1) in level_intervals else int(level_intervals[i]['min'])
            upper = int(level_intervals[i]['max'])
            seg_str = f"({lower}, {upper}]"
        
        result.append({
            '风险等级': level,
            '分段区间': seg_str,
            '分段数': int(row['分段数']),
            '占比': f"{row['分段总数占比']*100:.2f}%",
            '坏样本数': int(row['坏样本数']),
            '坏样本率': f"{row['坏样本率']*100:.2f}%"
        })
    
    return pd.DataFrame(result)


def calculate_lift_by_month_v2(score_df, search_pt, percentiles=[10, 5, 2, 1], y_='mob6_30', part_id='apply_mth', SCORE='scorecard_score'): 
    res = [] 
    for pt in search_pt: 
        aaa = score_df[score_df[part_id] == pt]  
        aaa = aaa[aaa[y_]>=0]
        lift_values = calculate_lift(aaa, y_col=y_ , score_col=SCORE, percentiles=[10, 5, 2, 1], lower_is_riskier=True) 
        lift_values['month'] = pt
        res.append(lift_values)
    aaa = score_df[score_df[part_id].isin(search_pt)] 
    aaa = aaa[aaa[y_]>=0]
    lift_values = calculate_lift(aaa, y_col=y_, score_col=SCORE, percentiles=[10, 5, 2, 1], lower_is_riskier=True)
    lift_values['month'] = 'all'
    res.append(lift_values)
    res_df = pd.DataFrame(res)
    return res_df[['month', '10%', '5%', '2%', '1%']]  


def calc_auc_ks_by_month_v2(df, target='target_mob6_30', score_col='score', sample_date='encash_date', sample_weight_col=''): 
    if len(df) < 2000000:
        tmp_df = df.copy()
    else:
        tmp_df = df 
    tmp_df['dt'] = tmp_df[sample_date].astype(str)
    auc_ks_by_month = calc_auc_ks_by_month(tmp_df, target, score_col, sample_date, sample_weight_col)
    lift_by_month = calculate_lift_by_month_v2(tmp_df, search_pt=auc_ks_by_month['观察点月'].tolist()[:-1], percentiles=[10, 5, 2, 1], y_='mob6_30', part_id='dt', SCORE=score_col)
    lift_by_month.rename(columns={'month': '观察点月'}, inplace=True)
    mrs = pd.merge(left=auc_ks_by_month, right=lift_by_month, on='观察点月', how='inner')
    return mrs