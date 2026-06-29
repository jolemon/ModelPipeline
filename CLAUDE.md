# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

`lgb2sql` 是一个自动化工具，将 LightGBM 模型的入模变量列表转换为 Hive SQL 变量拼接脚本，用于大数据风控场景中多变量表关联取数。核心价值：解析模型文件提取入模变量 → 结合变量元数据 → 自动生成完整 Hive SQL 拼接脚本。

## 常用命令

```bash
# 安装依赖（内网 PYPI 源）
pip install -r requirements.txt

# 一键执行完整 Pipeline
python run_full_pipeline.py

# 运行全部单元测试（24个）
python tests/test_all.py

# 运行回归测试（4个模型全量）
python tests/test_regression.py
python tests/test_regression.py --verbose

# 生成数据验证 SQL（9维度质量校验）
python scripts/analysis/generate_validation_sql.py \
    -m <model_id> -o <output_table> -s <sample_table>

# CSV 转 YAML 元数据
python scripts/convert_csv_to_metadata.py --input data/variable_dict.csv --output config/metadata.yaml

# 手动刷新元数据缓存
rm config/metadata.pkl
```

## 核心架构：Facade + Composition（P4 重构后）

项目经过 P0-P4 重构，每个核心模块采用 **Facade + 子组件委托** 模式：Facade 作为轻量级入口编排子组件，不直接承载业务逻辑。

### 包依赖关系（自上而下）

```
pipeline_pkg (流水线入口)
  ├── model_loaders (模型解析)
  ├── metadata (变量元数据)
  ├── core/config (配置加载)
  └── core (SQL 构建核心)
        └── core/sql/ (5 个 SQL 子组件)
```

### 关键包与职责

| 包 | Facade | 子组件 |
|---|--------|--------|
| `pipeline_pkg/` | `LgbToSqlPipeline` (~280行) 完整流程编排 | 5 个 Stage: Config / FeatureExtraction / MetadataReport / SQLGeneration / ScoreGeneration |
| `core/` | `SQLBuilder` (~320行) CTE/临时表风格 SQL | `FieldCollector`, `SubqueryBuilder`, `CreditGroupHandler`, `MergeTableBuilder`, `SQLFormatter` |
| `core/config/` | `SQLConfig` (~275行) 统一配置入口 | `ProjectConfig`, `SQLGenerationConfig`, `OutputConfig`, `PipelineConfig`, `OverrideConfig`, `CreditBridgeConfig` |
| `metadata/` | `MetadataManager` (~304行) 加载/查询/分组/检测/统计 | `VariableClassifier`, `OverrideApplier`, `MetadataStatistics` |
| `model_loaders/` | `load_model(path)` 自动根据后缀选择 | `PklModelLoader`, `PmmlModelLoader`, `TextModelLoader` |

### 数据流

```
模型文件(.pkl/.pmml/.model) → model_loaders → 变量列表
                                                      ↓
元数据(.yaml) → MetadataManager → 变量→表映射 (自动 .pkl 缓存加速 ~90x)
                                                      ↓
配置(.yaml) → SQLConfig → 样本表/输出表/控制策略
                                                      ↓
                    LgbToSqlPipeline.run()
                      ├── SQLBuilder → JOIN SQL (CTE 或 temp_table 风格)
                      └── ScoreGenerator → 打分 SQL (NVL→sigmoid→评分卡)
                                                      ↓
                                          完整 SQL 脚本 + Markdown 报告
```

## 配置系统

- **唯一入口**: `config/config.yaml`，支持 `${work_no}` / `${model_id}` / `${product_code}` 变量替换
- **五层配置**：换模型只需改第1-2层（project 标识 + model/sample/output 路径），第3-5层（业务规则/SQL参数/命名映射）一般不变
- **元数据自动缓存**：`metadata.yaml` 首次加载后自动生成 `metadata.pkl`，后续加载速度提升 ~90 倍（51s → 0.6s），修改 YAML 后自动重建缓存

## 模型格式支持

| 后缀 | 加载器 | 适用场景 |
|------|--------|---------|
| `.pkl` | `PklModelLoader` (pickle/joblib 回退) | Python 训练导出 |
| `.pmml` | `PmmlModelLoader` (内置 XML 解析) | 跨平台部署 |
| `.model` | `TextModelLoader` (纯文本解析) | LightGBM 原生 save_model |

## SQL 生成两条路径

1. **临时表风格** (`temp_table`): 按 (platform, join_key) 分组生成 DROP/CREATE TABLE AS，最终 JOIN 临时表到输出表 — 适合调度执行
2. **CTE 风格** (`cte`): 使用 WITH 子句 — 可读性好，适合分析调试

## 九大控制策略

SQL 生成行为由以下策略驱动，均通过 `config.yaml` 的 `sql_generation` 节控制：

1. **partition_control** — 分区控制：`range`（`>= min_partition`，回溯场景）vs `equality`（`= '${biz_date}'`），优先级 by_table > by_platform > by_category > default
2. **group_merge** — 组内合并：同一 (platform, join_key) 分组的多个临时表合并为一张总表
3. **credit_primary_table** — 征信桥接：样本表(cert_no) → 征信主键表(ci_rpt_id) → 征信变量表，支持 MD5 转换和时间窗口
4. **time_range_joins** — 时间区间匹配：`range` 模式（ROW_NUMBER 去重取最近一条）vs `equality` 模式（跨月精确匹配），支持 `direction: "between"`
5. **custom_join_conditions** — 自定义 JOIN：MD5 转换、时间偏移、完全自定义 ON 条件
6. **extra_where_conditions** — 额外 WHERE：by_table > by_platform > by_category
7. **歧义解析** — `platform` → `behavior_platform_priority` 顺序选择
8. **IN 子查询优化** — 变量子查询不限制分区等值，适配多分区回溯
9. **max_subquery_join** — 单临时表最大 JOIN 数，超出自动拆分

## SQL 验证工具

`tools/sql_validator.py` 自动生成 9 维度 Hive SQL 验证脚本：样本量一致性、变量缺失率、高缺失率变量、数据波动、环比波动、主键唯一性、评分分布、评分区间、变量覆盖度。

## 扩展点

- 新模型格式：`model_loaders/` 继承 `BaseModelLoader`
- 新 SQL 方言：`core/sql/sql_formatter.py` 扩展
- 新配置项：`core/config/` 新增子类并在 `SQLConfig` 中注册
- 新 Pipeline Stage：`pipeline_pkg/stages/` 新增 Stage 类

## 依赖

```
pandas>=1.3.0, pyyaml>=5.4, lightgbm>=3.3.0, joblib>=1.0.0, openpyxl>=3.0.0
```
