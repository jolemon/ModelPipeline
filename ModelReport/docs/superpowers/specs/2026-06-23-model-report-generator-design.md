# 模型报告生成器 — 设计文档

## 概述

信贷风控 LR 模型的报告生成器。输入已训练的评分卡对象 + 打分结果 DataFrame，输出 Excel 格式的多 sheet 模型报告。

**开发模式：TDD（测试驱动开发）**。先写测试用例，后写实现代码。

## 设计决策

| 决策点 | 选择 |
|--------|------|
| 调用方式 | Python 库 + CLI 命令行 |
| 评分卡对接 | 抽象接口 ScorecardProtocol，支持 .pkl 路径和已加载对象两种方式 |
| 定制空间 | 核心结构固定，列名/标签/分区名通过 ReportConfig 可配 |
| 变量元数据 | CSV/YAML 变量清单文件，无则留空 |
| 架构方案 | B：按 Sheet 拆分模块，ReportGenerator 做编排 |
| 指标计算 | 独立计算 KS/AUC/Lift/PSI，不依赖评分卡对象 |
| 设计原则 | 默认代替配置 |

## 项目结构

```
model_report/
├── __init__.py              # 公开 API: ReportGenerator, ScorecardProtocol, ReportConfig
├── interface.py             # ScorecardProtocol 抽象接口 + PickledScorecardAdapter
├── config.py                # ReportConfig: 列名映射 + 标签 + 阈值等可配置项
├── metadata.py              # 变量清单加载 (CSV/YAML → vardict)
├── metrics.py               # KS/AUC/Lift/PSI 独立计算函数（参考 model_learn.py）
├── generator.py             # ReportGenerator 编排器
├── cli.py                   # CLI 入口 (click)
├── writer.py                # ExcelWriter: openpyxl 写入 + 条件格式 (数据条)
├── sheets/
│   ├── __init__.py
│   ├── model_design.py      # Sheet 1: 模型设计 — 分区分布 + 建模分
│   ├── variable_analysis.py # Sheet 2: 变量分析 — IV/KS/PSI + Top10 WOE 分箱
│   └── model_performance.py # Sheet 3: 模型表现 — 评分卡详情 + 效果 + 回溯 + 分箱表现
tests/
├── test_metrics.py          # KS/AUC/Lift/PSI 计算函数
├── test_config.py           # 配置合并逻辑
├── test_model_design.py     # Sheet 1 builder
├── test_variable_analysis.py # Sheet 2 builder
├── test_model_performance.py # Sheet 3 builder
├── test_generator.py        # ReportGenerator 集成
└── conftest.py              # fixtures: sample_df, mock_scorecard
```

## 核心组件

### ScorecardProtocol (interface.py)

Protocol 类，定义报告生成器需要的评分卡信息。不依赖 scorecard_jsb.py。提供两个实现：

- `BinnerScorecardAdapter` — 适配已加载的 Binner/Scorecard 实例
- `PickledScorecardAdapter` — 从 .pkl 文件加载并自省

```python
class ScorecardProtocol(Protocol):
    def get_var_names(self) -> list[str]: ...
    def get_bins(self, var: str) -> pd.Series: ...
    def get_woe_table(self, var: str) -> pd.DataFrame: ...
    def get_iv_table(self) -> pd.Series: ...
    def get_ks_table(self) -> pd.Series: ...
    def get_model_summary(self) -> pd.DataFrame: ...
    def get_scorecard(self) -> pd.DataFrame: ...
    def get_missing_dict(self) -> dict: ...
    def get_dropped_vars(self) -> list[str]: ...
```

### ReportConfig (config.py)

dataclass，所有字段有默认值。可配置项：

- **列名映射**：`partition_col="part_id"`, `cust_col="cert_no"`, `date_col="loan_date"`, `target_col="mob6_30"`, `flag_col="data_flag"`, `score_col="pred_score"`, `sc_score_col="scorecard_score"`
- **标签映射**：`target_label="Mob6 30+"`, `train_label="训练集"`, `test_label="测试集"`, `oot_label="跨时间验证集"`, `oos_label="压测"`
- **Sheet 名称**：`sheet1_name="模型设计"`, `sheet2_name="变量分析"`, `sheet3_name="模型表现"`
- **阈值**：`top_n_vars=10`

### metrics.py — 独立计算的指标

参考 `model_library/model_learn.py` 中的实现，提取纯计算逻辑：

| 函数 | 来源参考 | 计算逻辑 |
|------|----------|----------|
| `calc_auc(y_true, y_score)` | `model_metrics_v4` | sklearn roc_auc_score |
| `calc_ks(y_true, y_score)` | `model_metrics_v4` | max(tpr - fpr) |
| `calc_lift(df, y_col, score_col, pcts)` | `calculate_lift` | top p% bad_rate / overall bad_rate |
| `calc_score_psi(df, score_col, flag_col)` | `psi_report` | 训练集 vs OOT 分数分布 PSI |
| `calc_bin_metrics(y, y_score, bins)` | `detailed_val_report` | 分箱 min/max/bad_rate/cum/KS/lift/cum_lift |
| `calc_monthly_metrics(df, target, score, date)` | `calc_auc_ks_by_month` | 逐月 AUC/KS/坏占比 |

### Sheet Builder 约定

每个 sheet 模块暴露一个构建函数，返回结构化数据（不含 Excel 写入逻辑）：

```python
def build_*_sheet(data: pd.DataFrame, scorecard: ScorecardProtocol, 
                  config: ReportConfig, metadata: dict) -> dict[str, pd.DataFrame]:
```

### ReportGenerator (generator.py)

编排器，调用 3 个 sheet builder，收集结构化数据，交由 ExcelWriter 写出。

```python
class ReportGenerator:
    def __init__(self, scorecard: ScorecardProtocol, config: ReportConfig | None = None): ...
    def generate(self, data: pd.DataFrame) -> ReportResult:
        # 调用 3 个 sheet builder
        ...
    def to_excel(self, output_path: str, data: pd.DataFrame | None = None): ...
```

### ExcelWriter (writer.py)

- 接收 `dict[str, DataFrame]` 结构化数据
- openpyxl 写入，支持：表头样式（粗体、背景色）、数字格式（百分比、小数位）、条件格式（数据条实心填充）、列宽自适应

### CLI (cli.py)

```
python -m model_report \
  --model model.pkl \
  --data score_result.csv \
  --output report.xlsx \
  --metadata vars.yaml \
  --config custom.toml
```

## 三个 Sheet 详细规格

### Sheet 1 — 模型设计

功能：`build_model_design_sheet(data, config) → dict[str, DataFrame]`，不依赖 ScorecardProtocol。

**1.1 样本分区分布**
- 分组：data_flag × part_id
- 列：样本数据集划分标签 | 样本分区 | 好 | 坏 | 总数 | 坏占比
- 行序：按 part_id 排列，末尾 "总计" 行

**1.2 样本建模分**
- 固定 4 行：训练集 / 测试集 / 跨时间验证集 / 总计
- 列：同 1.1（无样本分区列）

### Sheet 2 — 变量分析

功能：`build_variable_analysis_sheet(data, scorecard, config, metadata) → dict[str, DataFrame]`

**2.1 变量 IV/KS/PSI 总览表**
- 列：序号 | 变量名 | 变量解释含义（←metadata）| 来源（←metadata）| 表描述（←metadata）| 数据类型 | 缺失率_train | 缺失率_oot | iv_train | iv_oot | ks_train | ks_oot | psi
- 变量范围：所有数值特征列（排除配置中的非变量列）
- 按 IV_train 降序排列

**2.2 Top10 单变量 WOE 分箱分析**
- Top10 选取：按 IV_train 降序取前 10
- 每个变量一张子表，列：min | max | goods | bads | total | good_prop | bad_prop | bad_rate | woe | iv | ks | lift
- woe 列、bad_rate 列：条件格式-数据条-实心填充
- min 为左闭区间，max 为右开区间

### Sheet 3 — 模型表现

功能：`build_model_performance_sheet(data, scorecard, config) → dict[str, DataFrame]`

**3.1 评分卡详情**
- 来源：scorecard.get_model_summary()
- 列：Parameter | Estimate | Std-Error | Wald-Chi2 | P-value | P-value-num | Std | Std-Estimate | VIF

**3.2 建模样本集效果**
- 按 data_flag 分组 (train/test/oot)
- 列：样本集 | 观察点月 | 样本标签 | 总 | 好 | 坏 | 坏占比 | KS | AUC | 10%lift | 5%lift | 2%lift | 1%lift | train和各集合的PSI | 近期月对比各集合PSI

**3.3 全量回溯效果**
- 按 part_id 逐月展开，包含压测集（表现期未满的月份）
- 列结构同 3.2

**3.4 模型分箱表现**
- 每个 partition (train/test/oot + 各月度) 一张子表
- 列：min | max | bads | goods | total | bad_rate | cum_bad_rate | cum_bads_prop | ks | lift | cum_lift
- lift 列、cum_lift 列：条件格式-数据条-实心填充

## 错误处理

| 场景 | 策略 |
|------|------|
| 缺少必需列 | 抛 `DataValidationError`，列出缺失列名 |
| data_flag 缺少 train/test/oot | 抛 `DataValidationError` |
| target 不是 {0,1} | 抛 `DataValidationError` |
| 变量元数据文件缺失 | Warning，相关列填空字符串 |
| 变量分箱信息缺失 | 跳过该变量 WOE 表，标注 "未分箱" |
| 压测集缺失 (oos) | 可接受，3.3 中不生成 oos 行 |

## 依赖

```
pandas, numpy, scipy          # 已有
statsmodels                   # 已有 (scorecard_jsb)
scikit-learn                  # 新增: roc_auc_score
toad                          # 已有 (dataset_learn 引用)
openpyxl                      # 新增: Excel 写入 + 条件格式
click                         # 新增: CLI
```

## 与现有代码的关系

- **model_library/model_learn.py**：直接参考/适配 `model_metrics_v4`、`calc_auc_ks_by_month`、`calculate_lift`、`psi_report`、`detailed_val_report` 等函数的计算逻辑到 `metrics.py`。不直接 import（避免拉入 optuna/lightgbm 等无关依赖）。
- **model_library/scorecard_jsb.py**：通过 ScorecardProtocol 适配器间接使用，参考 Binner.woetables / Scorecard.show_model_result / Scorecard.generate_scorecard 的数据结构。
- **model_library/dataset_learn.py**：参考 `calc_missing`、`calc_psi`、`calc_iv` 的计算逻辑。

## 开发流程 (TDD)

1. 先写测试用例（tests/ 目录）
2. 确认测试失败
3. 实现功能代码
4. 确认测试通过
5. 重构优化

## 测试策略

- **单元测试** (pytest)：每个 sheet builder 独立可测，Mock ScorecardProtocol；指标计算函数已知预期值验证；配置合并逻辑
- **集成测试**：用 test.csv 作为输入，完整走通 generate() → Excel 输出
- **测试数据**：test.csv 包含 train/test/oot 三种 data_flag
