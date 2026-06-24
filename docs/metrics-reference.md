# 模型报告指标计算说明

> 适用版本：v0.1.0+
> 所有指标均**直接从打分数据计算**，不依赖评分卡 .pkl 文件。

---

## Sheet 2 — 变量分析

### 2.1 变量总览表

数据范围：仅含数值型特征列（排除 `part_id`、`cert_no`、`loan_date`、`mob6_30`、`data_flag`、`pred_score`、`scorecard_score` 及用户自定义排除列）。

#### 缺失率

$$
\text{缺失率} = \frac{\text{缺失样本数}}{\text{总样本数}}
$$

**缺失判定**（两条件满足其一）：
1. 值为 `NaN`
2. 数值 ≤ −99999（行业约定：`-999999`、`-99998` 等被视为缺失标记）

分别对 **train** 和 **oot** 子集计算，输出为百分比格式（如 `5.00%`）。

#### IV (Information Value)

$$
IV = \sum_{i} \left( \text{Bad}_i\% - \text{Good}_i\% \right) \times \ln\frac{\text{Bad}_i\%}{\text{Good}_i\%}
$$

**计算方式**：调用 `toad.quality(df[[var, target]], target, iv_only=True)`，由 toad 库自动完成最优分箱和 IV 计算。

分别对 **train** 和 **oot** 子集计算。

#### KS (Kolmogorov-Smirnov)

$$
KS = \max \left| F_{\text{bad}}(x) - F_{\text{good}}(x) \right|
$$

**计算方式**：`scipy.stats.ks_2samp(bad_values, good_values)`——对坏样本和好样本的变量值分布做双样本 KS 检验，取 KS 统计量。

$$
KS = \sup_x |F_{\text{bad}}(x) - F_{\text{good}}(x)|
$$

其中 $F_{\text{bad}}$ 和 $F_{\text{good}}$ 分别为坏/好样本在该变量上的经验累积分布函数。

分别对 **train** 和 **oot** 子集计算。

#### PSI (Population Stability Index)

$$
PSI = \sum_{i=1}^{10} \left( P_i^{\text{oot}} - P_i^{\text{train}} \right) \times \ln\frac{P_i^{\text{oot}}}{P_i^{\text{train}}}
$$

**计算方式**（等频分箱）：
1. 在 **train** 数据上做 10 等频分箱（`pd.qcut`，`q=10`）
2. 分箱边界两端扩展为 $[-\infty, +\infty]$，确保 oot 的所有值都能落入某个箱
3. 用同一套边界对 train 和 oot 分别计数
4. $P_i^{\text{train}} =$ 第 $i$ 箱 train 样本占比，$P_i^{\text{oot}} =$ 第 $i$ 箱 oot 样本占比
5. 缺失箱（某箱仅在一方存在）的占比填充 $10^{-10}$，避免 $\ln 0$

---

### 2.2 Top N 单变量 WOE 分箱表

按 IV 降序取前 N 个变量（默认 10），每个变量在 **train** 集上做等频分箱后计算以下指标。

**分箱方法**：
- 数值型变量：`pd.qcut(x, q=10)` 等频分 10 箱
- 类别型变量：每个唯一值为一箱

以下指标对每个分箱分别计算，并附加 ALL 汇总行。

#### 基础统计

| 列名 | 公式 | 说明 |
|------|------|------|
| `goods` | $\sum \mathbb{1}[\text{target}=0]$ | 箱内好样本数 |
| `bads` | $\sum \mathbb{1}[\text{target}=1]$ | 箱内坏样本数 |
| `total` | goods + bads | 箱内总样本数 |

#### 占比指标

| 列名 | 公式 | 说明 |
|------|------|------|
| `good_prop` | $\frac{\text{goods}}{\text{TotalGood}}$ | 该箱好样本占全体好样本比例 |
| `bad_prop` | $\frac{\text{bads}}{\text{TotalBad}}$ | 该箱坏样本占全体坏样本比例 |

> ALL 行：good_prop = 1.0, bad_prop = 1.0

#### WOE (Weight of Evidence)

$$
\text{WOE}_i = \ln\frac{\text{Bad}_i\%}{\text{Good}_i\%}
$$

其中 $\text{Bad}_i\%$、$\text{Good}_i\%$ 在 $\le 0$ 时截断为 $10^{-10}$。

- WOE > 0：该箱坏样本占比高于好样本占比（高风险箱）
- WOE < 0：该箱好样本占比高于坏样本占比（低风险箱）
- ALL 行：WOE = 0.0

#### IV（单箱贡献）

$$
\text{IV}_i = \left( \text{Bad}_i\% - \text{Good}_i\% \right) \times \text{WOE}_i
$$

ALL 行的 IV = 各箱 IV 之和 = 该变量总 IV。

#### KS（单箱）

$$
\text{KS}_i = \left| \text{Bad}_i\% - \text{Good}_i\% \right|
$$

ALL 行：KS = 0.0。

#### bad_rate

$$
\text{bad\_rate}_i = \frac{\text{bads}_i}{\text{total}_i}
$$

ALL 行：整体坏样本率 = TotalBad / TotalN。

#### Lift

$$
\text{Lift}_i = \frac{\text{bad\_rate}_i}{\text{OverallBadRate}}
$$

- Lift > 1：该箱坏样本率高于整体平均水平
- ALL 行：Lift = 1.0

---

## Sheet 3 — 模型表现

### 3.1 评分卡详情

仅在提供 `.pkl` 评分卡文件时生成。数据来源：`Scorecard.show_model_result()`。

| 列名 | 来源 | 说明 |
|------|------|------|
| Parameter | `model_result.params.index` | 变量名（含 intercept） |
| Estimate | `model_result.params` | 逻辑回归系数 $\beta$ |
| Std-Error | `model_result.bse` | 系数标准误 |
| Wald-Chi2 | $(\beta / \text{SE})^2$ | Wald 卡方统计量 |
| P-value | `1 - F_{\chi^2}(\text{Wald})$ | 显著性（`<.0001` 时为文本） |
| Std | 变量标准差 | $\sigma_x$ |
| Std-Estimate | $\beta \times \sigma_x / (\pi/\sqrt{3})$ | 标准化系数 |
| VIF | $\frac{1}{1-R^2}$ | 方差膨胀因子 |

### 3.2 建模样本集效果

按 `data_flag` 分组（train / test / oot），每组计算：

#### 基础统计

| 列名 | 公式 |
|------|------|
| 总 | $\text{Count}$ |
| 好 | $\sum \mathbb{1}[\text{target}=0]$ |
| 坏 | $\sum \mathbb{1}[\text{target}=1]$ |
| 坏占比 | $\frac{\text{坏}}{\text{总}}$ |

#### AUC

$$
\text{AUC} = \frac{\sum_{i \in \text{bad}} \sum_{j \in \text{good}} \mathbb{1}[\text{score}_i > \text{score}_j]}{N_{\text{bad}} \times N_{\text{good}}}
$$

调用 `sklearn.metrics.roc_auc_score(y_true, y_score)`。

#### KS

$$
KS = \max_{t} \left( \text{TPR}(t) - \text{FPR}(t) \right)
$$

其中 $\text{TPR}(t) = \frac{\text{TP}(t)}{\text{TP}(t)+\text{FN}(t)}$，$\text{FPR}(t) = \frac{\text{FP}(t)}{\text{FP}(t)+\text{TN}(t)}$，$t$ 为决策阈值。

调用 `sklearn.metrics.roc_curve` 后取 `max(tpr - fpr)`。

#### Lift (10% / 5% / 2% / 1%)

分数升序排列（低分=高风险），取最前面 p% 的样本：

$$
\text{Lift}_{p\%} = \frac{\text{BadRate}_{\text{top }p\%}}{\text{OverallBadRate}}
$$

- 分子：分数最低（风险最高）的前 p% 样本中的坏样本率
- 分母：全量样本的坏样本率

#### PSI（train 与各集合）

用评分卡分数列计算，train 分布作为 Expected，该集合作为 Actual：

$$
\text{PSI} = \sum_{i=1}^{10} \left( A_i - E_i \right) \times \ln\frac{A_i}{E_i}
$$

分箱方式：等宽 10 箱（`np.linspace(min, max, 11)`），两端扩展为 $[-\infty, +\infty]$。

### 3.3 全量回溯效果

按 `part_id`（月度）逐月展开。每月的 AUC / KS / Lift 计算方式同 3.2。

**PSI（首月与各集合）**：以第一个月的评分分布为 Expected，各月为 Actual。

**PSI（最近月对比各集合）**：以最近一个月的评分分布为 Expected，各月为 Actual。

末行为 **总计** 行，汇总全部样本。

### 3.4 模型分箱表现

对每个数据集（train / test / oot）和每个分区月，将 **评分卡分数** 等宽分 10 箱后计算。

**分箱**：`pd.cut(score, bins=10, include_lowest=True)`

#### 基础统计

| 列名 | 公式 |
|------|------|
| `bads` | 箱内坏样本数 |
| `goods` | 箱内好样本数 |
| `total` | 箱内总样本数 |

#### 率值指标

| 列名 | 公式 |
|------|------|
| `bad_rate` | $\frac{\text{bads}_i}{\text{total}_i}$ |
| `cum_bad_rate` | $\frac{\sum_{j=1}^{i} \text{bads}_j}{\sum_{j=1}^{i} (\text{bads}_j + \text{goods}_j)}$ |
| `cum_bads_prop` | $\frac{\sum_{j=1}^{i} \text{bads}_j}{\text{TotalBad}}$ |

> $i$ 为当前箱序号（按分数从低到高），`cum_bads_prop` 最后一箱必定为 1.0。

#### KS（累计）

$$
\text{KS}_i = \left| \frac{\text{CumBad}_i}{\text{TotalBad}} - \frac{\text{CumGood}_i}{\text{TotalGood}} \right|
$$

#### Lift

$$
\text{Lift}_i = \frac{\text{bad\_rate}_i}{\text{OverallBadRate}}
$$

#### cum_lift

$$
\text{cum\_lift}_i = \frac{\text{cum\_bad\_rate}_i}{\text{OverallBadRate}}
$$

---

## 附录 A：缺失值约定

| 判定条件 | 说明 |
|---------|------|
| `pd.isna(x)` | 标准 NaN |
| `x <= -99999` | 行业约定的缺失标记值 |

缺失值在计算缺失率时纳入统计，在等频分箱时被 `dropna()` 排除。

## 附录 B：分箱方法对比

| 场景 | 方法 | 箱数 | 边界 |
|------|------|------|------|
| 变量 PSI（Sheet 2.1） | 等频 `pd.qcut` | 10 | train 分位点 ± inf |
| 评分 PSI（Sheet 3.2/3.3） | 等宽 `np.linspace` | 10 | 全局 min/max ± inf |
| WOE 分箱（Sheet 2.2） | 等频 `pd.qcut` | 10 | 自动 |
| 分箱表现（Sheet 3.4） | 等宽 `pd.cut` | 10 | 自动 + `include_lowest=True` |

## 附录 C：第三方库调用

| 指标 | 库 | 函数 |
|------|-----|------|
| AUC | sklearn | `roc_auc_score` |
| KS（模型） | sklearn | `roc_curve` |
| KS（变量） | scipy | `stats.ks_2samp` |
| IV（变量总览） | toad | `quality(iv_only=True)` |
| 分箱 | pandas | `qcut` / `cut` |
