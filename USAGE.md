# 模型报告生成器 — 使用说明

> 版本：v0.1.0 | 测试：95 passed

## 目录

1. [安装](#安装)
2. [快速开始](#快速开始)
3. [输入数据格式](#输入数据格式)
4. [CLI 命令行](#cli-命令行)
5. [Python API](#python-api)
6. [配置项说明](#配置项说明)
7. [评分卡模型适配](#评分卡模型适配)
8. [变量元数据](#变量元数据)
9. [特征仓库自动分类](#特征仓库自动分类)
10. [输出报告说明](#输出报告说明)
11. [常见问题](#常见问题)

---

## 安装

### 依赖

```
pandas>=1.5.0, numpy>=1.24.0, scipy>=1.10.0, scikit-learn>=1.2.0
toad>=0.1.0, openpyxl>=3.1.0, click>=8.1.0
```

### 安装步骤

```bash
pip install dist/model_report-0.1.0-py3-none-any.whl
python3 -m model_report --help
```

---

## 快速开始

```bash
# 无评分卡，纯数据驱动
python3 -m model_report -d test.csv -o report.xlsx

# 带评分卡模型 — 自动限定分析范围为入模变量
python3 -m model_report -m model.pkl -d test.csv -o report.xlsx

# Python API
from model_report import ReportGenerator
ReportGenerator().to_excel("report.xlsx", df)
```

---

## 输入数据格式

### 必需列

| 默认列名 | 含义 | 取值格式 |
|---------|------|---------|
| `data_flag` | 数据集划分标签 | `train` / `test` / `oot` / `oos` |
| `mob6_30` | 样本标签 | `0`=未逾期，`1`=逾期 |
| 评分卡分数列 | 分数列（自动识别 `scorecard_score`/`score`/`pred_score`） | 数值 |

> `train`（训练集）**必须包含**。`test` / `oot`（跨时间验证集）建议包含。

### 可选列

| 默认列名 | 含义 | 取值格式 |
|---------|------|---------|
| `part_id` | 样本分区（可选，现从 `loan_date` 派生月份） | `yyyyMM` |
| `loan_date` | 样本发生时间 | `yyyy-MM-dd` |
| `cert_no` | 样本客户主键 | MD5 加密字符串 |
| `loan_amount` | 放款金额 | 数值，用于金额加权 AUC/KS |

### 特征列

排除上述列及 `exclude_columns` 后的所有数值列自动识别为特征。

### 缺失值约定

- `NaN` → 缺失
- 数值 ≤ `-99999` → 缺失（如 `-999999`）

---

## CLI 命令行

```bash
python3 -m model_report \
  -m model.pkl \        # 评分卡文件（可选）
  -d score_result.csv \  # 打分结果（必需）
  -o report.xlsx \       # 输出路径（默认 ./model_report.xlsx）
  --metadata vars.csv    # 变量元数据/特征仓库（可选）
```

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| `--model` | `-m` | 否 | `.pkl` 评分卡文件 |
| `--data` | `-d` | 是 | 打分结果 CSV（自动识别 Tab/逗号分隔） |
| `--output` | `-o` | 否 | 输出路径，默认 `./model_report.xlsx` |
| `--metadata` | | 否 | 元数据/特征仓库文件 |

---

## Python API

### 无评分卡

```python
from model_report import ReportGenerator
gen = ReportGenerator()
gen.to_excel("report.xlsx", df)
```

### 有评分卡

```python
from model_report import ReportGenerator, PickledScorecardAdapter
scorecard = PickledScorecardAdapter("model.pkl")
gen = ReportGenerator(scorecard)
gen.to_excel("report.xlsx", df)
```

### 自定义列名 + 金额加权

```python
from model_report import ReportConfig

config = ReportConfig(
    target_col="target_mob6_30",
    date_col="encash_date",
    sc_score_col="score",
    loan_amount_col="loan_amount",    # 放款金额列，启用金额加权 KS/AUC
    exclude_columns=["mob3_30", "mob2_15", "apl_chn"],  # 排除非特征列
)

gen = ReportGenerator(config=config)
gen.to_excel("report.xlsx", df, metadata_path="特征映射表.xlsx")
```

---

## 配置项说明

```python
@dataclass
class ReportConfig:
    # ── 列名映射 ──
    partition_col: str = "part_id"        # 样本分区列
    cust_col: str = "cert_no"            # 客户主键列
    date_col: str = "loan_date"          # 样本时间列（必须，用于派生月份）
    target_col: str = "mob6_30"          # 标签列（0/1）
    flag_col: str = "data_flag"          # 数据集划分标签列
    score_col: str = "pred_score"        # 模型原始分列
    sc_score_col: str = "scorecard_score" # 评分卡分数列（AUC/KS 计算优先使用）
    loan_amount_col: str = ""            # 放款金额列（启用金额加权 AUC/KS）

    # ── 排除列 ──
    exclude_columns: list = []            # Sheet 2 变量分析中排除的列名

    # ── 显示标签 ──
    target_label: str = "Mob6 30+"
    train_label: str = "训练集"
    test_label: str = "测试集"
    oot_label: str = "跨时间验证集"
    oos_label: str = "压测"

    # ── Sheet 名称 ──
    sheet1_name: str = "模型设计"
    sheet2_name: str = "变量分析"
    sheet3_name: str = "模型表现"

    # ── 阈值 ──
    top_n_vars: int = 10                 # WOE 分箱图展示前 N 个变量
```

---

## 评分卡模型适配

`PickledScorecardAdapter` 加载 `.pkl` 文件，导航 `Scorecard → Binner` 对象层级：

```
.pkl → Scorecard
        ├─ .binner → Binner
        │    ├─ .varlist        → 变量名列表
        │    ├─ .bins           → 各变量分箱区间
        │    ├─ .woetables      → 各变量 WOE 表
        │    ├─ .ivtable        → 各变量 IV 值
        │    └─ .missing_dict   → 缺失值填充映射
        ├─ .show_model_result() → 评分卡参数表
        └─ .score_card_result   → 评分卡分箱对照表
```

> 当评分卡成功加载后，Sheet 2 变量分析范围**自动限定为模型入模变量**，无需手动配置 `exclude_columns`。

---

## 变量元数据

元数据文件用于补充变量的业务含义（可选）。

### 通用 CSV 格式

```csv
变量名,变量解释含义,来源,表描述
txriskscorev7,三方风险分,edap.table_risk,外部数据-风险评分
```

---

## 特征仓库自动分类

传入 `.xlsx` 格式的特征映射表时，自动触发分类逻辑（与 `model_library/dataset_learn.py` 一致）：

| 检测条件 | 自动操作 |
|---------|---------|
| 包含列 `字段名` + `来源表` | 识别为特征仓库 |
| `字段含义` 列 | → `变量解释含义` |
| `来源表` 列 | → `来源` |
| 自动分类（`do_feature_category_classify`） | `行为变量` / `外部数据` / `征信变量` / `模型分` |
| 自动分类（`do_platform_classify`） | `百融` / `字节` / `京东白条` / ... |
| 分类拼接 | `表描述` = `类型-平台` |

特征仓库 Excel 示例：

| 字段名 | 字段含义 | 来源表 |
|--------|---------|--------|
| txriskscorev7 | 三方风险分 | edap.table_risk |
| l3m_cnsmcnt_sum | 近3个月总消费笔数 | wdyy.t_ccrdyyf_cust_cnsm_info_stats |

→ 自动输出：外部数据-外部数据、行为变量-字节

---

## 输出报告说明

### Sheet 1 — 模型设计

**样本分区分布** — 按 `loan_month` × `data_flag` 分组（train+test 合并为一行）

| 样本数据集划分标签 | 样本分区 | 好 | 坏 | 总数 | 坏占比 |
|-------------------|---------|----|----|------|--------|
| 训练测试集 | 202501 | ... | ... | ... | 1.92% |
| 跨时间验证集 | 202509 | ... | ... | ... | ... |
| 压测 | 202511 | ... | ... | ... | ... |
| 总计 | | ... | ... | ... | ... |

**样本建模分** — train/test/oot 汇总

### Sheet 2 — 变量分析

**变量总览** — 所有指标从打分数据计算，不依赖评分卡

| 列 | 说明 |
|----|------|
| iv_train / iv_oot | `toad.quality` 计算 |
| ks_train / ks_oot | `scipy.stats.ks_2samp` |
| psi | 等频分箱 PSI（train 基准） |
| 缺失率 | NaN + ≤ -99999 |

**Top10 单变量 WOE 分箱分析** — 单调分箱

- 等频 → 占比合并（≥3%）→ WOE 单调增加 → 箱数 4-6
- 缺失箱（MISSING_VALUE）前置
- ALL 汇总行

### Sheet 3 — 模型表现

**评分卡详情**（需评分卡）— Parameter / Estimate / Std-Error / Wald-Chi2 / P-value / VIF

**建模样本集效果** — train/test/oot 三行

| 列 | 说明 |
|----|------|
| KS / AUC | 评分卡分数计算（good_flag 为正类，auc(fpr,tpr) 梯形法） |
| 金额KS / 金额AUC | 仅在 `loan_amount_col` 配置时出现 |
| 10%/5%/2%/1% lift | 低分=高风险 |
| train和各集合的PSI | train 分 vs 各集合分（等频分箱） |
| 跨时间验证集对比各集合PSI | oot 分 vs 各集合分 |

**回溯效果** — 逐月 AUC/KS/PSI

- 月份从 `loan_date` 派生
- 分区标签由月内多数 flag 决定
- 训练测试集 → 跨时间验证集 → 压测 → 总计

**分箱表现** — 每集合/每月等频 10 箱

| 列 | 格式 |
|----|------|
| bad_rate / cum_bad_rate / cum_bads_prop | 0.00% |
| ks / lift / cum_lift | 0.00 |
| min / max | 整数（评分卡分数） |

---

## 常见问题

### Q: 没有 `.pkl` 文件？

可以。Sheet 2 所有指标仍从数据计算（iv_train/ks_train/WOE 等频分箱），Sheet 3 跳过评分卡详情。

### Q: WOE 分箱逻辑？

改编自 `model_library/dataset_learn.py` 的 `monotonic_binning`：等频微箱 → 占比合并 → WOE 单调增加 → 缺失箱前置。

### Q: 金额加权 AUC/KS？

```python
config = ReportConfig(loan_amount_col="loan_amount")
```
在 `sample_effect` 和 `backtest_effect` 中自动加入 `金额KS` / `金额AUC` 列。

### Q: 缺失值判定？

NaN 或 数值 ≤ -99999。

### Q: 测试？

```bash
pytest tests/ -v    # 95 passed
```
