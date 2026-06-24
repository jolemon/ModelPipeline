# 模型报告生成器 — 使用说明

## 目录

1. [安装](#安装)
2. [快速开始](#快速开始)
3. [输入数据格式](#输入数据格式)
4. [CLI 命令行](#cli-命令行)
5. [Python API](#python-api)
6. [配置项说明](#配置项说明)
7. [评分卡模型适配](#评分卡模型适配)
8. [变量元数据](#变量元数据)
9. [输出报告说明](#输出报告说明)
10. [常见问题](#常见问题)

---

## 安装

### 依赖

```
pandas>=1.5.0
numpy>=1.24.0
scipy>=1.10.0
scikit-learn>=1.2.0
toad>=0.1.0
openpyxl>=3.1.0
click>=8.1.0
```

### 安装步骤

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 验证安装
python3 -m model_report --help
```

---

## 快速开始

### 最简调用（无评分卡，纯数据驱动）

```bash
python3 -m model_report --data test.csv --output report.xlsx
```

### 带评分卡模型

```bash
python3 -m model_report --model model.pkl --data test.csv --output report.xlsx
```

### Python 调用

```python
import pandas as pd
from model_report import ReportGenerator, ReportConfig

df = pd.read_csv("test.csv", sep="\t")
gen = ReportGenerator()  # 无评分卡
gen.to_excel("report.xlsx", df)
```

---

## 输入数据格式

输入数据为 DataFrame / CSV 文件，包含以下列（列名可通过配置自定义）：

### 必需列

| 默认列名 | 含义 | 取值格式 | 是否必需 |
|---------|------|---------|---------|
| `part_id` | 样本分区 | `yyyyMM`（如 `202501`） | ✅ |
| `data_flag` | 数据集划分标签 | `train` / `test` / `oot` / `oos` | ✅ |
| `mob6_30` | 样本标签 | `0`=未逾期，`1`=逾期 | ✅ |
| `scorecard_score` | 评分卡分数 | 正整数，0-2位小数 | ✅ |

> `train`（训练集）、`test`（测试集）**必须包含**，`oot`（跨时间验证集）建议包含，`oos`（压测集）可选。

### 可选列

| 默认列名 | 含义 | 取值格式 |
|---------|------|---------|
| `cert_no` | 样本客户主键 | MD5 加密字符串 |
| `loan_date` | 样本发生时间 | `yyyy-MM-dd` |
| `pred_score` | 模型原始分数 | 0~1 之间 |

### 特征列

除上述列之外的所有列被自动识别为**特征变量列**。特征列应为**数值型**（`int64` / `float64`）。

### CSV 示例

```csv
part_id	cert_no	loan_date	mob6_30	data_flag	scorecard_score	txriskscorev7	feat_1	feat_2
202501	abc123	2025-01-06	0	train	650	47	0.023	1.5
202501	def456	2025-01-15	1	train	420	12	0.891	0.3
202506	ghi789	2025-06-20	0	oot	710	35	0.456	2.1
```

### 缺失值约定

数值 ≤ `-99999` 的值被视为缺失（如 `-999999`、`-99998`），与 `NaN` 同等处理。

---

## CLI 命令行

### 完整参数

```bash
python3 -m model_report \
  --model model.pkl \        # 评分卡文件路径（可选）
  --data score_result.csv \   # 打分结果 CSV 文件（必需）
  --output report.xlsx \      # 输出 Excel 路径（默认: ./model_report.xlsx）
  --metadata vars.csv         # 变量元数据文件（可选）
```

### 参数说明

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| `--model` | `-m` | 否 | `.pkl` 格式评分卡文件路径。若不提供，评分卡相关内容留空 |
| `--data` | `-d` | 是 | 打分结果文件，支持 `.csv` / `.xlsx` / `.xls` |
| `--output` | `-o` | 否 | 输出 Excel 路径，默认 `./model_report.xlsx` |
| `--metadata` | | 否 | 变量元数据文件，支持 `.csv` / `.yaml` / `.xlsx` |

### 使用示例

```bash
# 基本用法 — 无评分卡
python3 -m model_report -d test.csv

# 带评分卡模型 — 自动限定分析范围为入模变量
python3 -m model_report -m model.pkl -d test.csv -o report_2025Q1.xlsx

# 带变量元数据
python3 -m model_report -d test.csv --metadata feature_meta.csv
```

---

## Python API

### 导入

```python
from model_report import (
    ReportGenerator,      # 核心生成器
    ReportConfig,        # 配置类
    PickledScorecardAdapter,  # 评分卡适配器
)
```

### 无评分卡报告

```python
from model_report import ReportGenerator
import pandas as pd

df = pd.read_csv("test.csv", sep="\t")
gen = ReportGenerator()           # scorecard=None
gen.to_excel("report.xlsx", df)
```

### 有评分卡报告

```python
from model_report import ReportGenerator, PickledScorecardAdapter
import pandas as pd

df = pd.read_csv("test.csv", sep="\t")
scorecard = PickledScorecardAdapter("model.pkl")
gen = ReportGenerator(scorecard)
gen.to_excel("report.xlsx", df)
```

### 自定义列名映射

当输入数据的列名与默认值不同时，使用 `ReportConfig`：

```python
from model_report import ReportGenerator, ReportConfig
import pandas as pd

df = pd.read_csv("my_data.csv")

config = ReportConfig(
    partition_col="loan_month",     # 默认: "part_id"
    cust_col="appid",              # 默认: "cert_no"
    date_col="encash_date",        # 默认: "loan_date"
    target_col="target_mob6_30",   # 默认: "mob6_30"
    flag_col="data_flag",          # 默认: "data_flag"
    score_col="pred_score",        # 默认: "pred_score"
    sc_score_col="score",          # 默认: "scorecard_score"
)

gen = ReportGenerator(config=config)
gen.to_excel("report.xlsx", df)
```

### 带变量元数据

```python
from model_report import ReportGenerator, ReportConfig
import pandas as pd

df = pd.read_csv("test.csv", sep="\t")
config = ReportConfig()
gen = ReportGenerator(config=config)

# 传入元数据文件路径
gen.to_excel("report.xlsx", df, metadata_path="feature_meta.csv")
```

### 分步调用

```python
# 先生成结构化数据，再写入 Excel
sheets = gen.generate(df, metadata_path="vars.csv")
# sheets 是一个 dict: {"模型设计": {...}, "变量分析": {...}, "模型表现": {...}}

gen.to_excel("report.xlsx", df)
```

---

## 配置项说明

`ReportConfig` 所有字段及默认值：

```python
@dataclass
class ReportConfig:
    # ── 列名映射 ──
    partition_col: str = "part_id"        # 样本分区列
    cust_col: str = "cert_no"            # 客户主键列
    date_col: str = "loan_date"          # 样本时间列
    target_col: str = "mob6_30"          # 标签列（0/1）
    flag_col: str = "data_flag"          # 数据集划分标签列
    score_col: str = "pred_score"        # 模型原始分列（0~1）
    sc_score_col: str = "scorecard_score" # 评分卡分数列

    # ── 排除列 ──
    exclude_columns: list = []            # 排除的列名列表（如其他 target、渠道、ID 等）

    # ── 显示标签 ──
    target_label: str = "Mob6 30+"       # 标签含义
    train_label: str = "训练集"           # train 显示名
    test_label: str = "测试集"            # test 显示名
    oot_label: str = "跨时间验证集"       # oot 显示名
    oos_label: str = "压测"              # oos 显示名

    # ── Sheet 名称 ──
    sheet1_name: str = "模型设计"
    sheet2_name: str = "变量分析"
    sheet3_name: str = "模型表现"

    # ── 阈值 ──
    top_n_vars: int = 10                 # WOE 分箱图展示前 N 个变量
```

---

## 评分卡模型适配

### 工作原理

`PickledScorecardAdapter` 加载 `.pkl` 文件，自动导航 `Scorecard → Binner` 对象层级，提取报告所需的全部信息：

```
.pkl 文件
  └─ Scorecard（scorecard_jsb.py）
       ├─ .binner → Binner
       │    ├─ .varlist        → 变量名列表
       │    ├─ .bins           → 各变量分箱区间
       │    ├─ .woetables      → 各变量 WOE 表
       │    ├─ .ivtable        → 各变量 IV 值
       │    ├─ .missing_dict   → 缺失值填充映射
       │    └─ .drops          → 被剔除变量
       ├─ .show_model_result() → 评分卡参数表（Estimate / Wald / VIF）
       └─ .score_card_result   → 评分卡分箱对照表
```

> **注意**：当评分卡成功加载后，**变量分析范围自动限定为模型入模变量**（即 `get_var_names()` 返回的列表与数据列的交集）。无需手动配置 `exclude_columns`。

### 适配条件

`.pkl` 文件中的对象需满足以下条件之一：
- 拥有 `binner` 属性（指向 `Binner` 实例），且 `binner` 拥有 `woetables` 和 `ivtable`
- 直接拥有 `woetables` 和 `ivtable`（纯 `Binner` 对象）

### 自定义适配器

如果你的评分卡对象结构不同，可实现 `ScorecardProtocol` 接口：

```python
from model_report.interface import ScorecardProtocol

class MyScorecardAdapter:
    """适配自定义评分卡对象"""
    
    def __init__(self, my_scorecard):
        self._sc = my_scorecard

    def get_var_names(self) -> list[str]:
        return self._sc.feature_names

    def get_iv_table(self) -> "pd.Series":
        return self._sc.iv_values

    # ... 实现其余方法
```

---

## 变量元数据

元数据文件用于补充变量的业务含义（可选）。若未提供，报告中相关列留空。

### CSV 格式

```csv
变量名,变量解释含义,来源,表描述
txriskscorev7,三方风险分,edap.table_risk,外部数据-风险评分
l3m_cnsmcnt_sum,近3个月总消费笔数,wdyy.table_consume,贷中行为-消费状态
l24m_bal_add_ms,近24个月余额增加月份数,wdyy.table_balance,贷中行为-额度使用状态
```

### YAML 格式

```yaml
txriskscorev7:
  变量解释含义: 三方风险分
  来源: edap.table_risk
  表描述: 外部数据-风险评分
l3m_cnsmcnt_sum:
  变量解释含义: 近3个月总消费笔数
  来源: wdyy.table_consume
  表描述: 贷中行为-消费状态
```

### Excel 格式

与 CSV 同结构，第一列为变量名。

---

## 输出报告说明

生成的 Excel 文件包含 3 个 Sheet：

### Sheet 1 — 模型设计

**1.1 样本分区分布**
- 按 `data_flag` × `part_id` 分组
- 列：样本数据集划分标签 / 样本分区 / 好 / 坏 / 总数 / 坏占比
- 末行：总计

**1.2 样本建模分**
- 固定 4 行：训练集 / 测试集 / 跨时间验证集 / 总计
- 列：样本数据集划分标签 / 好 / 坏 / 总数 / 坏占比

### Sheet 2 — 变量分析

**2.1 变量总览表**
- 所有数值型特征（排除配置中的非变量列）
- 列：序号 / 变量名 / 变量解释含义 / 来源 / 表描述 / 数据类型 / 缺失率_train / 缺失率_oot / iv_train / iv_oot / ks_train / ks_oot / psi
- 按 `iv_train` 降序排列

**2.2 Top N 单变量 WOE 分箱表**
- 按 IV 降序取前 N 个变量（默认 10）
- 每个变量一张子表：min / max / goods / bads / total / good_prop / bad_prop / bad_rate / woe / iv / ks / lift
- 含 "ALL" 汇总行
- `good_prop` / `bad_prop` / `bad_rate` 格式化为百分比
- `woe` / `bad_rate` 列有条件格式（数据条）

### Sheet 3 — 模型表现

**3.1 评分卡详情**（需评分卡）
- 列：Parameter / Estimate / Std-Error / Wald-Chi2 / P-value / P-value-num / Std / Std-Estimate / VIF

**3.2 建模样本集效果**
- 按 `data_flag` 分组（train / test / oot）
- 列：样本集 / 观察点月 / 样本标签 / 总 / 好 / 坏 / 坏占比 / KS / AUC / 10%lift / 5%lift / 2%lift / 1%lift / train和各集合的PSI / 近期月对比各集合PSI

**3.3 全量回溯效果**
- 按 `part_id` 逐月展开（含压测集）
- 列结构同 3.2，PSI 替换为首月/最近月对比

**3.4 模型分箱表现**
- 每个数据集（train / test / oot）+ 每个分区月 各一张表
- 列：min / max / bads / goods / total / bad_rate / cum_bad_rate / cum_bads_prop / ks / lift / cum_lift
- `lift` / `cum_lift` 列有条件格式（数据条）

---

## 常见问题

### Q: 没有 `.pkl` 评分卡文件，能生成报告吗？

可以。评分卡文件为可选项。不提供时：
- Sheet 2 的 `iv_train`/`ks_train`/WOE 表仍从数据等频分箱计算
- Sheet 3 的「评分卡详情」不生成
- 其他内容均正常输出

### Q: 数据列名与默认值不同怎么办？

通过 `ReportConfig` 指定实际列名，见[配置项说明](#配置项说明)。

### Q: 支持哪些数据格式？

输入数据：CSV（逗号或 Tab 分隔）、Excel（`.xlsx` / `.xls`）
输出报告：Excel（`.xlsx`）

### Q: 缺失值如何处理？

- `NaN` → 视为缺失
- 数值 ≤ `-99999` → 视为缺失（如 `-999999`、`-100000`）
- 缺失率 = 总缺失数 / 总样本数

### Q: 报错 `ModuleNotFoundError: statsmodels`？

```bash
pip install statsmodels
```
仅在使用评分卡 `.pkl` 文件时需要，因为 `scorecard_jsb.py` 依赖它。

### Q: 报错 `NameError: name 'tubao' is not defined`？

这是 `scorecard_jsb.py` 中 `Binner.var_coarse_bin` 的依赖，不影响报告生成。报告生成器不依赖粗分箱功能（`model_report` 不 import `model_library`）。

### Q: 如何只生成部分 Sheet？

使用 Python API 分步调用：

```python
from model_report.sheets.model_design import build_model_design_sheet

# 只生成 Sheet 1
result = build_model_design_sheet(df, config)
```

### Q: 测试如何运行？

```bash
pytest tests/ -v
```
