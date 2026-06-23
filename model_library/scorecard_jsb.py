import pandas as pd
import numpy as np 
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.outliers_influence import variance_inflation_factor
class Binner:
    """
    Binner类，用于对指定数据集进行分箱操作，主要涉及细分箱、粗分箱、IV计算、WOE计算、WOE值替换。
    
    
    """
    def __init__(self,data:pd.DataFrame=None, varlist:list=None, target:str=None, weight:str=None,vardict:dict=None,missing_dict:dict=None,drops:dict =None,bins:dict=None ,if_store_woe=True) :
        """
        构造函数，可选输入data、target、weight。
        data：数据集，不输入无法工作
        varlist:特征列表，不输入会取排除target列、weight列之外的所有列名
        target：标签列名，不输入默认取第一列，不会校对是否为{0,1}取值列。
        
        vardict: 特征字典（中文说明），非必须，不输入则后续结果不包含任何特征的中文注释
        missing_dict: 缺失值填充字典，会按照对应的键值对填充变量缺失值，后续分箱时会尝试将该值单独分箱
        """
        self.data = pd.DataFrame(data) if data is None else data
        self.varlist = varlist
        if self.data.shape[0] == 0:
            print('No Data')
            raise Exception('No Data')
        if target is None:
            self.target = self.data.columns[0]
            print(f'Not given target col, choose the first column: {self.target}.')
        else:
            self.target = target
        target_unique =sorted(data[target].unique())
        if data[target].nunique()!= 2 or target_unique[0]!=0 or target_unique[1]!=1:
            print(f'target column values are not [0,1]. check target values')
            raise Exception('target Error')     
        self.weight = weight
        if varlist is None:
            self.varlist = list(self.data.columns)
            if target in self.varlist:
                self.varlist.remove(target)
            if weight in self.varlist:
                self.varlist.remove(weight)
        else:
            self.varlist = varlist
        self.vardict = {} if vardict is None else vardict
        self.missing_dict = {} if missing_dict is None else missing_dict
        self.bins = {}  if bins is None else bins
        # self.manualbins = {}
        self.woetables = {}
        self.ivtable = pd.Series([],name='IV')
        self.maxtotpct = pd.Series([],name='maxtot_pct')
        self.maxbadpct = pd.Series([],name='maxbad_pct')
        self.mintotpct = pd.Series([],name='mintot_pct')
        self.minbadpct = pd.Series([],name='minbad_pct')
        # self.missingpct = pd.Series([],name='missing_pct')
        self.drops = {}  if drops is None else drops
        self.if_store_woe = if_store_woe
        if if_store_woe:
            self.data_woe = self.data[[target]].copy()
            self.data_woe['intercept'] = np.ones(self.data_woe.shape[0])
        for var in self.missing_dict.keys():
            self.data.fillna({var:self.missing_dict.get(var)},inplace=True)
            
    def update_missing_dict(self,var,fillna):
        """
        更新缺失值， ATTENTION 注意会将所有等于原缺失值 的均替换为新缺失值，无论其原本是否是缺失的状态。
        var: 需要更新的变量名
        fillna: 更新后的缺失值填充值
        """
        old_fillna = self.missing_dict.get(var)
        if old_fillna is None:
            self.missing_dict[var] = fillna
            self.data.fillna({var:fillna},inplace=True)
        else:
            self.missing_dict[var] = fillna
            self.data.replace({var:old_fillna},fillna,inplace=True)
            self.data.fillna({var:fillna},inplace=True)

    
    def varlist_apply_bin(self,varlist=None):
        """
        批量应用分箱， 会将提供的变量列表中的变量分箱应用。主要用于手动修改分箱和传入已有分箱记录后的应用。
        varlist: 变量列表
        """
        if varlist is None:
            varlist = list(self.bins.keys())
        length = len(varlist)
        for p,var in enumerate(varlist):
            print('\r',end='')
            print(f'''应用分箱中，进度：{(p+1)/(length):.2%}: {(p+1):>4} / {length:>4} |{'='*int((p+1)/(length)*49)+('>' if p < (length-1) else '=')+' '*(49-int((p+1)/(length)*49))}| 当前变量：{var:>50}''',end='\t')
            self.var_apply_bin(var)

    
    def varlist_coarse_bin(self,varlist=None,if_miss=False):
        """
        批量粗分箱， 会将提供的变量列表中的变量进行粗分箱
        varlist: 变量列表
        """
        if varlist is None:
            varlist = list(self.bins.keys())
        length = len(varlist)
        for p,var in enumerate(varlist):
            print('\r',end='')
            print(f'''粗分箱中，进度：{(p+1)/(length):.2%}: {(p+1):>4} / {length:>4} |{'='*int((p+1)/(length)*49)+('>' if p < (length-1) else '=')+' '*(49-int((p+1)/(length)*49))}| 当前变量：{var:>50}''',end='\t')
            self.var_coarse_bin(var,if_miss)

    def varlist_fine_bin(self,varlist=None,bins=20,force_rebin=False):
        """
        批量细分箱， 会将提供的变量列表中的变量进行细分箱
        varlist: 变量列表
        bins:分箱数
        force_rebin:是否强制重新分箱，如果false，那对于已经在bins中有值的变量不会重新分箱。
        """
        if varlist is None:
            varlist = self.varlist
        length = len(varlist)
        for p,var in enumerate(varlist):
            print('\r',end='')
            print(f'''细分箱中，进度：{(p+1)/(length):.2%}: {(p+1):>4} / {length:>4} |{'='*int((p+1)/(length)*49)+('>' if p < (length-1) else '=')+' '*(49-int((p+1)/(length)*49))}| 当前变量：{var:>50}''',end='\t')
            if not force_rebin and self.ivtable.get(var) is not None:
                continue
            self.var_fine_bin(var,bins)
            

    def var_apply_bin(self,var):
        """
        应用分箱， 会将提供的变量分箱应用。主要用于手动修改分箱和传入已有分箱记录后的应用。
        var: 变量
        """
        bin_var = f"_bin_{var}"
        bins = self.bins.get(var)
        if bins is None:
            print(f"var: {var} hasn't been bin, check the bin result use bins['{var}'] ")
            return 
        if self.data[var].dtype.name in ["float","float64","int64","int","int32","float32"]:
            df_bin = pd.DataFrame(self.data[[var,self.target]+([self.weight] if self.weight else [])])
            
            print(bins)
            df_bin[bin_var] = pd.cut(self.data[var],bins.dropna(),precision=3, right=False).astype('object')
            if self.weight is None:
                df_woe = pd.crosstab(df_bin[bin_var],df_bin[self.target],dropna=False).fillna(0).astype(np.float64)
            else :
                df_woe = pd.crosstab(df_bin[bin_var],df_bin[self.target],df_bin[self.weight],aggfunc='sum',dropna=False).fillna(0).astype(np.float64)
            df_woe['Total'] = df_woe.sum(1)
        else:
            print(f'类别性变量：{var}, 强制转换类型为str, 默认填充缺失值为 "missing" ')
            if self.missing_dict.get(var) is None:
                self.update_missing_dict(var,'missing')
            self.data[var] = self.data[var].astype(str)
            df_bin = pd.DataFrame(self.data[[var,self.target]+([self.weight] if self.weight else [])])
            df_bin[bin_var] = ""
            for i in self.bins[var] :
                df_bin.loc[df_bin[var].isin(i),bin_var] =pd.Series( (i,)*df_bin.shape[0],index=df_bin.index)
            if self.weight is None:
                df_woe = df_bin.groupby([bin_var,self.target],dropna=False)['target'].count().unstack().fillna(0)
            else :
                df_woe = df_bin.groupby([bin_var,self.target],dropna=False)[self.weight].sum().unstack().fillna(0)
            df_woe['Total'] = df_woe.sum(1)
        self.gen_woe_table(var,df_woe)
        if not self.if_store_woe:
            return 
        self.data_woe[var] = df_bin[bin_var].apply(self.woetables[var]['WoE'].to_dict().get)
    
    def var_fine_bin(self,var,bins=20):
        """
        细分箱， 会将提供的变量进行细分箱，默认强制重新分箱
        var: 变量
        bins:分箱数
        """
        if self.drops.get(var) is not None:
            print(f'dropped var: {var}, pass.')
            return 
        bin_var = f"_bin_{var}"
        vartype = self.data.dtypes[var]
        if vartype  not in  ["float","int64","float64","int","float32","int32"]:
            print(f'类别性变量细分箱：{var}, 强制转换类型为str, 默认填充缺失值为 "missing" ')
            if self.missing_dict.get(var) is None:
                self.update_missing_dict(var,'missing')
            self.data[var] = self.data[var].astype(str)
            df_bin = pd.DataFrame(self.data[[var,self.target]+([self.weight] if self.weight else [])])
            df_bin[bin_var] = df_bin[var].apply(lambda x:(x,))
            if self.weight is None:
                df_woe = df_bin.groupby([bin_var,self.target],dropna=False)['target'].count().unstack().fillna(0)
            else :
                df_woe = df_bin.groupby([bin_var,self.target],dropna=False)[self.weight].sum().unstack().fillna(0)
            df_woe['Total'] = df_woe.sum(1)
            self.bins[var] = pd.Series(df_bin[bin_var].unique())
            self.gen_woe_table(var,df_woe)
            if not self.if_store_woe:
                return 
            self.data_woe[var] = df_bin[bin_var].apply(self.woetables[var]['WoE'].to_dict().get)    
        elif vartype.name in  ["float","int64","float64","int","float32","int32"]:
            if_miss = self.data[var].isnull().any()
            nunique = self.data[var].nunique() + (1 if if_miss else 0)
            if nunique <= 1:
                self.drops[var] = 'Only 1 unique value'
                print(f'{var} has only 1 unique value, drop.')
                return
            else:
                df_bin = pd.DataFrame(self.data[[var,self.target]])
                df_bin[bin_var],bins_t = pd.qcut(self.data[var],bins,precision=3,duplicates='drop',retbins=True)
                for i in range(len(bins_t)):
                    bins_t[i] = bins_t[i].round(3)
                bins_t = sorted(pd.Series(bins_t).unique())
                fillna = self.missing_dict.get(var)
                if fillna is not None and self.data[var].eq(fillna).any():
                    if fillna not in bins_t:
                        bins_t.append(fillna)
                        bins_t = sorted(bins_t)
                    bins_t.insert(bins_t.index(fillna),fillna-1e-3)
                    
                bins_t.insert(0,-np.inf)
                if len(bins_t)==1:
                    bins_t.append(np.inf)
                else:
                    bins_t[-1] = np.inf
                self.manual_bin_numeric(var,cutpts=bins_t)
    def drop_vars(self,iv_thres=0.02,maxtotpct_thres=0.98):
        for var in self.varlist:
            if self.drops.get(var) is not None:
                continue
            if self.ivtable.get(var) <iv_thres:
                self.drops[var] = 'Low IV'
                print(f'var:{var} dropped cause of Low IV')
            elif self.maxtotpct.get(var) > maxtotpct_thres:
                self.drops[var] = '集中度过高'
                print(f'var:{var} dropped cause of 集中度过高')
        

    def gen_woe_table(self,var,df_woe):
        """
        woe table生成函数， 一般不直接对外交互，不想写注释
        """
        df_woe.columns = ["Good","Bad","Total"]
        df_woe.loc['All'] = df_woe.sum(0)
        df_woe_pct = df_woe.div(df_woe.iloc[-1])
        df_woe_pct.columns = ["%Good","%Bad","%Total"]
        df_woe_pctcum = df_woe_pct.cumsum(axis=0)
        df_woe_pctcum.iloc[-1] = (1,1,1)
        df_woe_pctcum.columns = ["Cum %Good","Cum %Bad","Cum %Total"]
        df_woe_pct["WoE"] = np.log(df_woe_pct["%Good"]/df_woe_pct["%Bad"])
        df_woe_pct.replace({"WoE":np.inf},0,inplace=True)
        df_woe_pct["IV"] = (df_woe_pct.WoE*(df_woe_pct["%Good"]-df_woe_pct["%Bad"]))
        df_woe_pct.loc['All',"IV"] = np.nansum(df_woe_pct.IV)
        df_all = pd.concat([df_woe,df_woe_pct,df_woe_pctcum],axis=1)
        df_all["Bad Rate"] = (df_all.Bad/df_all.Total).round(10)
        df_all["Lift"] = (df_all.Bad/df_all.Total/(df_all.Bad.sum()/df_all.Total.sum())).round(4)
        df_all["bin_num"] = list(range(len(df_all)))
        self.bins[var] = pd.Series(list(df_all.index[:-1]),name = 'bins')
        self.woetables[var] = df_all
        self.ivtable[var] = df_all.IV.iloc[-1].astype(float)
        self.maxtotpct[var] = df_all["%Total"][:-1].max()
        self.maxbadpct[var] = df_all["%Bad"][:-1].max()
        self.mintotpct[var] = df_all["%Total"][:-1].min()
        self.minbadpct[var] = df_all["%Bad"][:-1].min()


    def var_coarse_bin(self,var,if_miss=True):
        """
        粗分箱， 会将提供的变量进行粗分箱（合箱）
        var: 变量
        """
        if self.drops.get(var) is not None:
            print(f'dropped var: {var}, pass.')
            return 
        if self.data[var].dtype.name not in  ["float","int64","float64","int","float32","int32"]:
            print(f"None-numeric var: {var}, won't be coarse bin. ")
            return 
        binning = self.bins[var]
        n = 0
        for x in binning:
            if x.right > self.missing_dict.get(var,-np.inf) or if_miss == False:
                break
            n += 1
        df_result2 = self.woetables[var][n:(-1 if np.nan not in list(binning) else list(binning).index(np.nan))]
        if df_result2["Bad"].sum() <1 or df_result2["Good"].sum() < 1:
            print(f"target has only 1 unique value, won't be coarse bin. ")
            return 
        #display(df_result2)
        cum_list_up = [(0, 0), (0, 1)]
        cum_list_low = [(0, 0), (1, 0)]

        cum_bad=df_result2["Bad"].cumsum()/df_result2["Bad"].sum()
        cum_good=df_result2["Good"].cumsum()/df_result2["Good"].sum()
        for i in range(0, df_result2.shape[0]):
            cum_list_up.append((cum_bad.iloc[i], cum_good.iloc[i]))
        for i in range(0, df_result2.shape[0]):
            cum_list_low.append((cum_bad.iloc[i], cum_good.iloc[i]))
        #print(cum_list_up)
        #print(cum_list_low)
        result_up = tubao.convex_hull(cum_list_up)
        result_low = tubao.convex_hull(cum_list_low)
        area_up = tubao.GetAreaOfPolyGonbyVector(result_up)
        area_low = tubao.GetAreaOfPolyGonbyVector(result_low)
        result_up_zh = pd.DataFrame(result_up)
        result_low_zh = pd.DataFrame(result_low)
        # 新的bin合并
        merge_lst = []
        last = int(df_result2.iloc[0].bin_num)
        end = int(df_result2.iloc[-1].bin_num)
        if area_up > area_low:
            for i in range(1,result_up_zh.shape[0]-1):
                kt = df_result2[cum_bad == result_up_zh[0][i]].bin_num.values[0]
                # print(result_up_zh[0][i],cum_bad,last,kt)
                if last <= kt:
                    if last < kt:
                        merge_lst.append([last,kt])
                    last = kt + 1
        else:
            for i in range(result_low_zh.shape[0]-1,1,-1):
                #print(result_low_zh[0][i])
                # print(i)
                kt = df_result2[cum_bad == result_low_zh[0][i]].bin_num.values[0]
                # print(result_low_zh[0][i]==cum_bad,kt,end)
                if last <= kt:
                    if last < kt:
                        merge_lst.append([last,kt])
                    last = kt + 1      # print(merge_lst)
        self.manual_bin_numeric(var,merge_lst=merge_lst)


    def manual_bin_numeric(self,var,merge_lst:list=None,cutpts:list=None):
        """
        手动分箱，仅适用于数值型变量
        var:变量名
        merge_list: a two_dimentional list which has vals of length 2 list
        cutpts : list which has vals of float
        """
        if merge_lst is None and cutpts is None:
            raise Exception("None manual change put in args. check the args.")
        if merge_lst is not None and cutpts is not None:
            raise Exception('Both merge_list and cutpts are given, check the args.')
        if merge_lst is not None:
            
            bins = self.bins[var]
            tmp = None  
            newbins = list(self.bins[var])
            for merge_i in merge_lst:
                if tmp is not None:
                    if merge_i[0]<tmp[1]:
                        raise Exception('merge_lst should not be overlapping.')
                tmp = merge_i
                if len(merge_i) != 2 or merge_i[1]<= merge_i[0]:
                    raise Exception('merge_lst val length should be 2, and merge_lst[1] > merge_lst[0] ')
               
                bin_ins = pd.Interval(self.bins[var][merge_i[0]].left,self.bins[var][merge_i[1]].right)
                for i in range(merge_i[0],merge_i[1]+1):
                    newbins[i] = bin_ins
            self.bins[var] = pd.Series(newbins,name = 'bins').unique()
            self.var_apply_bin(var)
        if cutpts is not None:
            if len(cutpts) <= 1:
                raise Exception('cutpts length should be >1 ')
            newbins = []
            tmp = None
            for i in cutpts:
                if tmp is None :
                    tmp = i
                    continue
                newbins.append(pd.Interval(tmp,i))
                tmp = i
            self.bins[var] = pd.Series(newbins,name = 'bins')
            self.var_apply_bin(var)

    def display_woetables(self,varlst=None):
        if varlst is not None:
            lst = varlst
        else:
            lst = self.woetables.keys()
        for var in lst:
            a = self._woe_styling(var)
            display(a)

    def _woe_styling(self,var):
        styles = [
            dict(selector="caption", props=[("text-align", "left"),("font-size", "150%"),("color", "red")])
        ]
        df_woe = self.woetables[var]
        desc = self.vardict.get(var,'')
        return df_woe.style.bar(subset=['WoE'],align='mid',color=['#d65f5f', '#5fba7d']).set_table_styles(styles).set_caption("%s-%s"%(var,desc)).format({'%Good': "{:.2%}", '%Bad': "{:.2%}",'%Total':"{:.2%}",'Bad Rate':"{:.2%}"})

    def var_psi_cal(self, var, data, label='test',precision = None ,if_detail= True):
        """
        单变量psi计算，根据输入的变量名var、数据集data、数据集名label（可选，默认test）返回psi计算过程以及结果（if_detail控制是否输出过程），precision控制结果精度（默认None，不限制输出精度）。
        入参
            var: 字符串类型，含义：要计算psi的变量名  
            data： DataFrame， 含义：计算psi的数据集
            label：字符串， 含义：数据集名称
            precision：int ，含义：结果精度
            if_detail:bool, 含义：是否显示过程
        返回值：
            DataFrame，计算过程 或 float 计算结果
        """
        if self.bins.get(var,None) is None:
            print(f'{var} 尚未分箱，请先分箱')
            return None
        data_fillna = data.fillna(self.missing_dict)
        if self.data[var].dtype.name in ["float","float64","int64","int","int32","float32"]:
            train_dist = (pd.cut(self.data[var],self.bins[var].dropna(), right=False).value_counts(dropna=False).sort_index()/self.data.shape[0]).rename('train_dist')
            data_dist = (pd.cut(data_fillna[var],self.bins[var].dropna(), right=False).value_counts(dropna=False).sort_index()/data.shape[0]).rename(f'{label}_dist')
        else:
            data_fillna[var] = data_fillna[var].astype(str)
            train_bin = pd.DataFrame(self.data[[var]])
            data_bin = pd.DataFrame(data_fillna[[var]])


            train_bin["__bin__"] = ""
            data_bin["__bin__"] = ""
            for i in self.bins[var] :
                train_bin.loc[train_bin[var].isin(i),"__bin__"] =pd.Series( (i,)*train_bin.shape[0],index=train_bin.index)
                data_bin.loc[data_bin[var].isin(i),"__bin__"] =pd.Series( (i,)*data_bin.shape[0],index=data_bin.index)
            train_dist = (train_bin["__bin__"].value_counts(dropna=False).sort_index()/train_bin.shape[0]).rename('train_dist')
            data_dist = (data_bin["__bin__"].value_counts(dropna=False).sort_index()/data_bin.shape[0]).rename(f'{label}_dist')
        res = pd.concat([train_dist,data_dist],axis = 1).fillna(0)
        res[f'{label}_psi'] = np.log(res['train_dist']/res[f'{label}_dist'])*(res['train_dist']-res[f'{label}_dist'])
        res.loc['TOTAL'] = res.sum(0)
        if precision is not None:
            res = res.round(precision)
        if if_detail == True:
            return res
        return res.loc['TOTAL',f'{label}_psi']
        
    def varlist_psi_cal(self, varlist, data, label='test', precision = None):
        """
        psi批量计算，批量调用var_psi_cal,详见其注释。
        """        
        if varlist is None:
            varlist = self.varlist
        length = len(varlist)
        res = pd.Series([],name = f'{label}_psi')
        for p,var in enumerate(varlist):
            print('\r',end='')
            print(f'''psi计算中，进度：{(p+1)/(length):.2%}: {(p+1):>4} / {length:>4} |{'='*int((p+1)/(length)*49)+('>' if p < (length-1) else '=')+' '*(49-int((p+1)/(length)*49))}| 当前变量：{var:>50}''',end='\t')
            res.loc[var] = self.var_psi_cal(var,data,label,precision,False)
        return res
                


class Scorecard:
    def __init__(self,binner:Binner=None,varlist:list=None):
        self.binner = binner
        self.weight = binner.weight
        if varlist is None or not isinstance(varlist,list):
            self.varlist = self.binner.varlist
        else:
            self.varlist = varlist
        self.model = None
        self.model_result = None
        self.model_perf = None
        self.train_score_rank  = None
        self.test_score_rank = None
        self.all_score_rank = None
        self.corr_matrix = None
        self.train_score_dist = None
        self.test_score_dist = None
        self.all_score_dist = None
        self.model_vars = []
        self.dropped_vars = list(self.binner.drops.keys())
        self.var_pushin = 'intercept'
        self.model_scorecard = None
        self.df_effect = pd.DataFrame(columns=['Parameter', 'Score-Chi2', 'P-value', 'P-value-num'])

    def fit(self,invars=None):
        if invars is not None:
            self.model_vars = list(invars)
        X_in = self.binner.data_woe[self.model_vars]
        tmp_model = sm.GLM(self.binner.data_woe[self.binner.target],X_in,family=sm.families.Binomial(),freq_weights = np.ones(self.binner.data_woe.shape[0]) if self.weight is None else self.binner.data[self.weight])
        tmp_model_result = tmp_model.fit()
        df_wald = self.show_model_result(tmp_model_result)
        self.model = tmp_model
        self.model_result = tmp_model_result
        display(self.show_model_result())
        
    def LR_single_step(self,p_val_thres = 1e-2,corr_thres=0.7, vif_thres=4,detail= True ):
        # print(self.var_pushin) 
        
        X_in = self.binner.data_woe[self.model_vars+[self.var_pushin]]
        corr = (X_in.corr()-np.eye(X_in.shape[1],X_in.shape[1])).max().max()
        if corr>corr_thres:
            print(f'var: {self.var_pushin} dropped cause of corr > {corr_thres} after it pushed in')
            self.dropped_vars.append(self.var_pushin)
            self.df_effect.drop(self.df_effect[self.df_effect.Parameter.eq(self.var_pushin)].index,inplace=True )
            return 
        tmp_model = sm.GLM(self.binner.data_woe[self.binner.target],X_in,family=sm.families.Binomial(),freq_weights = np.ones(self.binner.data_woe.shape[0]) if self.weight is None else self.binner.data[self.weight])
        tmp_model_result = tmp_model.fit()
        
        
        df_wald = self.show_model_result(tmp_model_result)
        display(df_wald)
        # df_wald['VIF'] = 
        # print(corr)
        max_pval = df_wald['P-value-num'].max()
        if X_in.shape[1]<=1:
            vif = 0
        else:
            vif = pd.Series([variance_inflation_factor(X_in,i) for i in range(X_in.shape[1])]).max()
        if df_wald.Estimate.ge(0).any():
            print(f'var: {self.var_pushin} dropped cause of at least 1 estimate > 0 after it pushed in')
            self.dropped_vars.append(self.var_pushin)
            self.df_effect.drop(self.df_effect[self.df_effect.Parameter.eq(self.var_pushin)].index,inplace=True )
        elif corr>corr_thres:
            print(f'var: {self.var_pushin} dropped cause of corr > {corr_thres} after it pushed in')
            self.dropped_vars.append(self.var_pushin)
            self.df_effect.drop(self.df_effect[self.df_effect.Parameter.eq(self.var_pushin)].index,inplace=True )
        elif vif>vif_thres:
            print(f'var: {self.var_pushin} dropped cause of vif > {vif_thres} after it pushed in')
            self.dropped_vars.append(self.var_pushin)
            self.df_effect.drop(self.df_effect[self.df_effect.Parameter.eq(self.var_pushin)].index,inplace=True )
        else:
            while max_pval > p_val_thres:
                self.model_vars = list(df_wald.sort_values('P-value-num')['Parameter'])[:-1]
                self.dropped_vars +=  list(df_wald.sort_values('P-value-num')['Parameter'])[-1:]
                X_in = self.binner.data_woe[self.model_vars]
                tmp_model = sm.GLM(self.binner.data_woe[self.binner.target],X_in,family=sm.families.Binomial(),freq_weights = np.ones(self.binner.data_woe.shape[0]) if self.weight is None else self.binner.data[self.weight])
                tmp_model_result = tmp_model.fit()
                df_wald = self.show_model_result(tmp_model_result)
                max_pval = df_wald['P-value-num'].max()
            self.model_vars = list(df_wald['Parameter'])
            self.model = tmp_model
            self.model_result = tmp_model_result
            if detail:
                display(self.show_model_result())
            self.var_pushin = None


    def show_model_result(self,model_result=None):
        if model_result is not None:
            tmp_model_res = model_result
        else:
            tmp_model_res = self.model_result
        # display(tmp_model_res.params)
        df_wald = pd.DataFrame(columns=['Parameter', 'Estimate', 'Std-Error', 'Wald-Chi2', 'P-value', 'P-value-num'])
        df_wald['Parameter'] = tmp_model_res.params.index.values
        df_wald['Estimate'] = tmp_model_res.params.tolist()
        df_wald['Std-Error'] = tmp_model_res.bse.tolist()
        df_wald['Wald-Chi2'] = (df_wald['Estimate'] / df_wald['Std-Error']) ** 2
        df_wald['Std'] = df_wald.Parameter.apply(self.binner.data_woe.std().get)
        df_wald['Std-Estimate'] = df_wald['Estimate'] * df_wald['Std'] / (np.pi / np.sqrt(3))
        # chi-square distribution with one degree of freedom
        df_wald['P-value-num'] = 1 - stats.chi2.cdf(df_wald['Wald-Chi2'], 1)
        df_wald['P-value'] = df_wald['P-value-num'].astype('str')
        # change the display format of small p-values
        ids = df_wald[df_wald['P-value-num'] < 0.0001].index.tolist()
        df_wald.loc[ids, 'P-value'] = '<.0001'
        if df_wald.shape[0]>1:
            df_wald['VIF'] = pd.Series({list(df_wald['Parameter']).index(vart):variance_inflation_factor(self.binner.data_woe[df_wald['Parameter']],list(self.binner.data_woe[df_wald['Parameter']].columns).index(vart)) for vart in df_wald['Parameter']})
        return df_wald.sort_values('Wald-Chi2',ascending=False).reset_index(drop=True)
        
    def test_var_to_pushin(self):
        for var in self.varlist:
            X_in = self.binner.data_woe[self.model_vars+[var]]
            corr = (X_in.corr()-np.eye(X_in.shape[1],X_in.shape[1])).max().max()
            if corr == 1:
                self.dropped_vars.append(var)
                continue
            if var in self.model_vars or var in self.dropped_vars:
                continue
            else:
                print(var)
                scores, p_values, df_level = self.model.score_test(self.model_result.params, exog_extra=self.binner.data_woe[var])
                if p_values[0] < 0.0001:
                    p_value = '< .0001'
                else:
                    p_value = str(p_values[0])
                self.df_effect.loc[len(self.df_effect.index)] = {'Parameter': var, 'Score-Chi2': scores[0], 'P-value': p_value, 'P-value-num': p_values[0]}


    # def backward_single_step(self):
    #     if len(self.model_vars)<=1 :
    #         return 
    def stepwise(self,p_val_thres = 1e-2,corr_thres=0.7, vif_thres=4,detail= True,max_step = 100 ):  
        step = 0
        self.model_vars=[]
        self.var_pushin='intercept'
                
        while step <= max_step:
            print(f"=========== step {step}. {'intercept push in ' if step == 0 else 'test '+str(self.df_effect.shape[0])+' vars to push in'  } =============")
            if step ==0 :
                self.LR_single_step(p_val_thres=p_val_thres,corr_thres=corr_thres,vif_thres=vif_thres,detail = detail)
            elif self.df_effect.shape[0]==0:
                print('No More Parameter can be pushed in. Quit stepwise.')
                break
            else:
                while self.df_effect.shape[0]>0:
                    # print('df_effect.shape[0] :', self.df_effect.shape[0])
                    self.var_pushin = self.df_effect.loc[self.df_effect['Score-Chi2'].idxmax(),'Parameter']
                    print('当前被选中加入模型的变量:', self.var_pushin)
                    self.LR_single_step(p_val_thres=p_val_thres,corr_thres=corr_thres,vif_thres=vif_thres,detail = detail)
                    # print(self.df_effect.shape[0])
                    if self.var_pushin is None:
                        print(f'变量成功加入')
                        break
                    
                    print(self.df_effect.shape[0])
                else:
                    print('候选变量数量', self.df_effect.shape[0])
                    if self.var_pushin is not None and self.df_effect.shape[0]==0:
                        print('No More Parameter can be pushed in. Quit stepwise.')
                        break
                        
            if self.df_effect.shape[0]>0:
                self.df_effect.drop(self.df_effect.index,inplace=True)
            self.test_var_to_pushin()
            display(self.df_effect)
            step += 1
        else:
            print(f'iteration reached max step {max_step}, quit stepwise.')


    def generate_scorecard(self,missing_dict={},base_score=600, base_odd=20,score_step=50):
        """记分卡生成函数
        参数：
        missing_dict: 缺失值映射
        base_score: 基础分
        base_odd: 基础好坏比
        score_step: 步进分

        函数逻辑： 根据 Scorecard.model_result 中的 系数  以及 binner中的woe分箱计算各分箱对应分值。
            注意：1. 各入模变量分箱不会保留负分，负分部分会合并到截距项。
                  
        
        """
        _missdict = self.binner.missing_dict|missing_dict
        styles = [
            dict(selector="caption", props=[("text-align", "center"),("font-size", "200%"),("color", "blue")])
        ]
        model_result = self.show_model_result()
        varlst = self.model_vars
        woe_list = self.binner.woetables
        factor = score_step / np.log(2)
        offset = base_score - factor * np.log(base_odd)
        intercept = model_result[model_result.Parameter=="intercept"].Estimate.values[0]
        scorecard = {}
        min_score_all = 0
        for x in range(len(varlst)):
            var = varlst[x]
            if var == 'intercept':
                continue
            woe_tab = woe_list[var].copy()
            woe_tab["coef"] = model_result[model_result.Parameter==var].Estimate.values[0]
            score_org = woe_tab.WoE * (-1) * factor * woe_tab.coef
            min_score_all += min(score_org)
            score_adj = score_org - min(score_org)
            scorecard[var] = score_adj
        const_score = offset + (-1) * intercept * factor
        scorecard['intercept'] = pd.Series({'ALL':const_score+min_score_all},name=0)
        scorecard['intercept'].index.name='bin'
        # print(scorecard)
        
        a = []
        b = []
        # varlst = varlst
        for x in range(len(varlst)):
            # print(varlst[x])
            # print(scorecard[var])
            var = varlst[x]  
            t = pd.DataFrame(round((scorecard[var]).astype(float)))
            # display(t)
            miss_val = _missdict.get(var,np.nan)
            if var =='intercept' :
                # continue
                data = [[var,"","",score] for bin,score in zip([''],t[0])]
            elif self.binner.data[var].dtype.name not in  ["float","int64","float64","int","float32","int32"]:
                data = [[var,bin if bin != -99999 else np.nan,"__none_numeric__",score] for bin,score in zip(self.binner.bins[var],t[0])]
            else:
                data = [[var,np.nan if pd.isnull(bin)  else bin.left,np.nan if pd.isnull(bin)  else bin.right,score  ] for bin,score in zip(self.binner.bins[var],t[0])]
                
            
            tmp = pd.DataFrame(data,columns=["name","left","right","score"])
            # print(var,miss_index)
            if pd.notnull(miss_val):
                ind = -1
                for row in tmp.copy().itertuples():
                    ind+=1
                    if self.binner.data[var].dtype.name in  ["float","int64","float64","int","float32","int32"] and row.left<miss_val and miss_val <=row.right:
                        data.insert(ind,[var,np.nan,np.nan,row.score])
                
                tmp = pd.DataFrame(data,columns=["name","left","right","score"])
                # print(data)
            if var!='intercept' and self.binner.data[var].dtype.name in  ["float","int64","float64","int","float32","int32"] and not pd.isnull(tmp.left.idxmin()) :
                tmp.loc[tmp.left.idxmin(),'left'] = -np.inf
            b.append(tmp)
        self.score_card_result = pd.DataFrame(pd.concat(b)).set_index('name')   
        return self.score_card_result

    
    def display_scorecard_with_intercept(self,missing_dict={},base_score=600, base_odd=20,score_step=50):
        styles = [
            dict(selector="caption", props=[("text-align", "center"),("font-size", "200%"),("color", "blue")])
        ]
        missing_dict = self.binner.missing_dict|missing_dict
        model_result = self.show_model_result()
        varlst = self.model_vars
        woe_list = self.binner.woetables
        factor = score_step / np.log(2)
        offset = base_score - factor * np.log(base_odd)
        intercept = model_result[model_result.Parameter=="intercept"].Estimate.values[0]
        scorecard = {}
        min_score_all = 0
        for x in range(len(varlst)):
            var = varlst[x]
            if var == 'intercept':
                continue
            woe_tab = woe_list[var].copy()
            woe_tab["coef"] = model_result[model_result.Parameter==var].Estimate.values[0]
            score_org = woe_tab.WoE * (-1) * factor * woe_tab.coef
            min_score_all += min(score_org)
            score_adj = score_org - min(score_org)
            scorecard[var] = score_adj
        const_score = offset + (-1) * intercept * factor
        scorecard['intercept'] = pd.Series({'ALL':const_score+min_score_all},name=0)
        scorecard['intercept'].index.name='bin'
        # print(scorecard)
        a = []
        b = []
            # varlst = varlst
        # varlst =  varlst
        for x in range(len(varlst)):
            #print(scorecard[var])
            var = varlst[x]  
            t = pd.DataFrame(round((scorecard[var]).astype(float)))
            # display(t)
            if var =='intercept':
                data = [[var,'',score] for bin,score in zip([''],t[0])]
            elif self.binner.data[var].dtype.name not in  ["float","int64","float64","int","float32","int32"]:
                data = []
                for bin,score in zip(self.binner.bins[var],t[0]):
                    if bin == -99999:
                        data.append([var,"missing",score])
                    elif -99999 in bin:
                        data.append([var,f"{var} in {bin}, missing",score])
                    else:
                        data.append([var,f"{var} in ({bin})",score])
            else:
                data = []
                min_to_inf = True
                for bin,score in zip(self.binner.bins[var],t[0]):
                    if  pd.isnull(bin):
                        data.append([var,"missing",score])
                    else:
                        if min_to_inf:
                            data.append([var,f"{var} <= {bin.right}" ,score])
                            min_to_inf = False
                        elif bin.right == np.inf:
                            data.append([var,f" {bin.left} < {var}" ,score])
                        else:
                            data.append([var,f" {bin.left} < {var} <= {bin.right}" ,score])
                        
                # data = [["missing" if bin.left==-99999.001 and bin.right==-99999 else f"{bin.left} < {var} <= {bin.right}" ,score] for bin,score in zip(self.binner.bins[var],t[0])]
            tmp_bins = self.binner.bins.get(var,[])
            for tmp_index in range(len(tmp_bins)):
                if pd.isnull(tmp_bins[tmp_index])  or missing_dict.get(var,np.nan) in tmp_bins[tmp_index]:
                    miss_index = tmp_index
                    break
            else:
                miss_index = None
            # print(var,miss_index)
            if miss_index != None:
                data[miss_index][1] += ', missing'
    
            b.append(pd.DataFrame(data,columns=['var',"bins","score"]))
        return pd.DataFrame(pd.concat(b)).set_index(['var','bins'])
