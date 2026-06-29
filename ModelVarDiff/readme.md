# model-var-diff

## 概述

算法模型投产后，需要校验线上线下变量取值的一致性。本工具自动化完成两个 CSV 数据集的变量对比，生成 Markdown 分析报告。

**核心能力**：空值处理、分数容差比较、精度感知比较、多级上钻分析、单变量异常排查 SQL。

## 目录结构

```
lion/
├── readme.md
├── VALIDATION_RULES.md
├── pyproject.toml
├── requirements.txt
├── model_var_diff/               # 主包
│   ├── main.py
│   ├── config_loader.py
│   ├── comparator.py
│   ├── analyzer.py
│   └── report_generator.py
├── model_loaders/                # 模型文件加载器
│   ├── base.py
│   ├── text_loader.py
│   ├── pkl_loader.py
│   └── pmml_loader.py
├── config/
│   └── variables.json
└── data/
    ├── online.csv / offline.csv
    └── vars.txt
```

## 快速开始

### 1. 安装

```bash
pip install dist/model_var_diff-0.2.0-py3-none-any.whl
```

依赖：`pandas`、`numpy`。

### 2. 运行

三种配置方式三选一：

```bash
# 方式一：JSON 配置
model-var-diff --config config/variables.json --online ... --offline ...

# 方式二：变量名列表
model-var-diff --var-list data/vars.txt --pk user_id --score model_score --online ... --offline ...

# 方式三：模型文件（自动解析变量名）
model-var-diff --model model.lgb --pk user_id --score model_score --online ... --offline ...
```

## 特征库（可选）

提供特征库 CSV 后，工具自动匹配 `字段名 → 来源表`，上钻分析按数据源粒度归因。

格式支持两种：
- **含 `来源表` 列**：直接用作数据源
- **含 `库名` + `表名` 列**：自动拼接 `库名.表名`（参照 `data/demo/特征映射表_新底座_20260601.csv`）

```bash
model-var-diff --var-list vars.txt --feature-warehouse feature_warehouse.csv ...
```

## 校验规则

详见 [VALIDATION_RULES.md](VALIDATION_RULES.md)。

## 输出报告

### 1. 输入数据概况
### 2. 分数校验结果
### 3. 变量校验结果（按数据源→变量二级排序）
### 4. 上钻分析（严格 / 75% / 50% / 25% / 宽松）
### 5. 单变量分析（空值维度 + Top3 取值对 + 排查 SQL）
### 附录：校验规则全文

## CLI 参数

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--config` | 三选一 | - | JSON 配置文件路径 |
| `--var-list` | 三选一 | - | 变量名列表文件 |
| `--model` | 三选一 | - | 模型文件（.model/.pkl/.pmml） |
| `--pk` | 非 JSON 时必填 | `user_id` | 主键列名 |
| `--score` | 否 | `model_score` | 模型分列名 |
| `--score-online` | 否 | 同 `--score` | 线上 score 列名 |
| `--score-offline` | 否 | 同 `--score-online` | 线下 score 列名 |
| `--sep` | 否 | `,` | CSV 分隔符 |
| `--feature-warehouse` | 否 | - | 特征库文件路径 |
| `--online` | 是 | - | 线上 CSV |
| `--offline` | 是 | - | 线下 CSV |
| `--output` | 否 | `output` | 输出目录 |

## 技术栈

Python 3.9+ · pandas · numpy · 纯 CLI
