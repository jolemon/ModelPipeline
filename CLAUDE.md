# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言规范

所有对话和文档都使用中文。

## 仓库概述

这是一个信贷风控模型工具链的 monorepo，包含三个独立的 Python 子项目，按风控模型生命周期排列：

```
模型文件(.pkl/.model/.pmml)
    ↓
Lgb2Sql   ──→ 生成 Hive SQL 变量拼接脚本（特征取数）
    ↓
ModelVarDiff ──→ 校验线上线下变量一致性（投产验证）
    ↓
ModelReport  ──→ 生成 Excel 模型报告（LR 评分卡报告）
```

三个子项目各自独立打包、独立运行，但共享风控领域概念（变量、特征表、分箱、WOE/IV/KS/PSI）。

## 子项目速览

| 项目 | 入口 | 安装方式 |
|------|------|---------|
| `Lgb2Sql/` | `python run_full_pipeline.py` | `pip install -r requirements.txt` |
| `ModelVarDiff/` | `model-var-diff` CLI | `pip install dist/model_var_diff-*.whl` |
| `ModelReport/` | `python3 -m model_report` CLI | `pip install dist/model_report-*.whl` |

每个子项目有独立的 `CLAUDE.md`，包含各自的架构、命令和扩展点。处理具体子项目时**优先阅读对应的 CLAUDE.md**：
- [Lgb2Sql/CLAUDE.md](Lgb2Sql/CLAUDE.md) — LightGBM → Hive SQL 生成器
- [ModelVarDiff/claude.md](ModelVarDiff/claude.md) — 线上线下变量 diff 工具
- [ModelReport/CLAUDE.md](ModelReport/CLAUDE.md) — LR 模型报告生成器

## 跨项目关系

1. **Lgb2Sql 的输出 → ModelVarDiff 的输入**：Lgb2Sql 生成的 SQL 用于 Hive 取数，取数结果（CSV）可直接用 ModelVarDiff 做线上线下对比
2. **Lgb2Sql 和 ModelVarDiff 共用模型解析模式**：两者都能解析 `.pkl`/`.pmml`/`.model` 提取入模变量，但实现独立（各自维护 `model_loaders/` 或等价模块）
3. **ModelReport 消费 Lgb2Sql + 打分引擎的下游产物**：Lgb2Sql 提供变量取数 SQL → Hive 执行 → 模型打分 → CSV 结果 → ModelReport 生成报告
4. **共享风控概念**：三个项目都涉及 WOE、IV、KS、PSI、分箱、评分卡、特征重要性等概念；ModelReport 的 `model_library/` 包含参考实现 (`scorecard_jsb.py`/`dataset_learn.py`) ，ModelVarDiff 的 `ref/` 引用了它的分箱逻辑

## 通用约定

- Python 3.9+，内网 PYPI 源
- 列名默认小写下划线命名，CSV 读取时自动 `.str.lower()` 归一化
- 缺失值哨兵：业务侧约定 `<= -99999`（如 `-999999`）视为缺失
- 尽量采用默认代替配置——所有构造函数参数均有默认值
- 评分卡基准：base_score=600, base_odd=20, score_step=50（ModelReport 的 readme.md）
