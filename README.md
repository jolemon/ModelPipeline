# ModelPipeline

信贷风控模型工具链 monorepo，覆盖模型投产的完整生命周期。

## 工具链流程

```
模型文件(.pkl/.model/.pmml)
    │
    ▼
Lgb2Sql          ──→  Hive SQL 变量拼接脚本（特征取数）
    │
    ▼
ModelVarDiff     ──→  线上线下变量一致性校验（投产验证）
    │
    ▼
ModelReport      ──→  Excel 模型报告（LR 评分卡报告）
```

## 子项目

| 项目 | 功能 | 使用方式 |
|------|------|---------|
| [Lgb2Sql](./Lgb2Sql/) | LightGBM 模型 → Hive SQL | `python run_full_pipeline.py` |
| [ModelVarDiff](./ModelVarDiff/) | 线上线下变量 diff | `model-var-diff --config ...` |
| [ModelReport](./ModelReport/) | LR 评分卡报告生成 | `python3 -m model_report -d data.csv -o report.xlsx` |

各子项目的详细文档见对应的 CLAUDE.md。

## 共享模块

`shared/` 目录提供三个项目共用的代码：

```
shared/
├── model_loaders/     ← 模型变量提取（.pkl/.pmml/.model）
├── model_library/     ← 评分卡建模参考实现（Binner/Scorecard）
├── metadata/          ← 特征仓库加载 + 变量分类（表名→类型/平台）
└── utils.py           ← 缺失值判定、日期转换等工具函数
```

## 通用约定

- Python 3.9+
- 缺失值哨兵 `<= -99999`
- CSV 列名自动 `.str.lower()` 归一化
- 评分卡基准：base_score=600, base_odd=20, score_step=50
- 尽量采用默认代替配置
