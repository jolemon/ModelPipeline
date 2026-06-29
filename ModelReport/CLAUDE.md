# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

信贷风控领域的 LR 模型报告生成器。输入评分卡模型文件（.pkl）和打分结果（CSV），输出 Excel 格式的多 sheet 模型报告。

## 架构

核心代码在 `model_library/scorecard_jsb.py`，包含两个主要类：

- **`Binner`** — 变量分箱引擎。负责细分箱（等频）、粗分箱（凸包合箱）、WOE/IV/KS 计算、WOE 值替换、PSI 计算。分箱结果存储在 `self.bins`、`self.woetables`、`self.ivtable` 等属性中。
- **`Scorecard`** — 评分卡建模引擎。依赖 `Binner` 实例，负责逐步回归（stepwise LR with VIF/相关性/显著性检验）、评分卡生成（base_score=600, base_odd=20, score_step=50）、模型效果评估。

数据流：`pandas.DataFrame` → `Binner`（分箱+WOE）→ `Scorecard`（逐步回归+评分卡）→ Excel 报告（按 readme.md 中定义的三个 sheet 输出）。

## 技术栈与依赖

- Python, pandas, numpy, statsmodels, scipy
- `tubao` 模块：`Binner.var_coarse_bin` 中用于凸包计算的辅助模块（`tubao.convex_hull`、`tubao.GetAreaOfPolyGonbyVector`），目前未在项目中提供，需要从外部引入。

## 关键约定

- **尽量采用默认代替配置**：构造函数参数均有默认值，列名约定如 readme.md 所述（`part_id`、`cert_no`、`loan_date`、`mob6_30`、`data_flag`、`pred_score`、`scorecard_score`）。
- 目标列必须为 `{0, 1}` 二分类，否则 `Binner.__init__` 会抛异常。
- 缺失值处理：通过 `missing_dict` 映射填充值，分箱时填充值会被单独处理。

## 当前状态

- 项目尚未模块化：所有逻辑在单一 .py 文件中，无 `setup.py`/`pyproject.toml`/`requirements.txt`。
- 无测试。无 CLI 入口。`readme.md` 是功能规格说明，包含报告输出的详细格式定义。
- `tubao` 模块缺失——运行 `var_coarse_bin` 会因导入错误失败。
