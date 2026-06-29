# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

信贷风控领域的 LR 模型报告生成器。输入评分卡模型文件（.pkl）和打分结果（CSV），输出 Excel 格式的多 sheet 模型报告。

## 常用命令

```bash
# 安装
pip install dist/model_report-*.whl

# CLI 使用
python3 -m model_report -d test.csv -o report.xlsx                # 纯数据驱动
python3 -m model_report -m model.pkl -d test.csv -o report.xlsx   # 带评分卡
python3 -m model_report -m model.pkl -d test.csv --metadata vars.csv -o report.xlsx

# 运行测试（95 passed）
pytest tests/ -v

# 生成样本报告
python generate_sample_report.py
```

## 架构

```
model_report/                    ← CLI 包
├── __main__.py                  ← 入口 (python -m)
├── cli.py                       ← Click CLI
├── config.py                    ← ReportConfig dataclass
├── metrics.py                   ← AUC/KS/PSI/Lift/WOE 计算
├── metadata.py                  ← 变量元数据加载 + 特征库分类
├── interface.py                 ← PickledScorecardAdapter
├── generator.py                 ← 报告编排引擎
├── writer.py                    ← Excel 写入
└── sheets/                      ← 三个 Sheet 的渲染逻辑
```

数据流：`CSV` → `ReportGenerator` → `metrics.py`（计算指标）+ `interface.py`（加载评分卡）→ `writer.py`（Excel）→ `report.xlsx`

## 共享模块依赖

项目使用 `shared/` 目录下的共享代码：

| 模块 | 用途 |
|------|------|
| `shared/model_library/scorecard_jsb.py` | `Binner` / `Scorecard` 评分卡引擎（通过 pickle 加载） |
| `shared/utils.py` | `calc_missing_rate`, `to_month`, `MISSING_THRESHOLD` |
| `shared/classifier.py` | `classify_category`, `classify_platform` 特征库分类 |
| `shared/model_library/config.py` | 全局配置（特征仓库路径等） |

## 关键约定

- **尽量采用默认代替配置**：所有 `ReportConfig` 构造函数参数均有默认值
- 目标列必须为 `{0, 1}` 二分类，否则 `Binner.__init__` 会抛异常
- 缺失值哨兵：`<= -99999` 视为缺失（定义在 `shared/utils.py:MISSING_THRESHOLD`）
- 列名约定：`part_id`、`cert_no`、`loan_date`、`mob6_30`、`data_flag`、`pred_score`、`scorecard_score`
- 评分卡基准：base_score=600, base_odd=20, score_step=50
- 缺失值处理：`PickledScorecardAdapter` 从 Binner 获取 `missing_dict` 映射

## 输出报告

三个 Sheet：模型设计（样本分布 + 建模分）→ 变量分析（IV/KS/PSI + Top10 WOE 分箱）→ 模型表现（评分卡详情 + 样本效果 + 回溯效果 + 分箱表现）

## 已知限制

- `shared/model_library/scorecard_jsb.py` 的 `Binner.var_coarse_bin` 依赖外部 `tubao` 模块（凸包合箱），目前未提供
