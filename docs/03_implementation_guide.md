# lgb2sql 实现详解

> 本文档包含模块详细说明、SQL生成示例和控制策略详解。

---

## 项目结构

```
lgb2sql_project/
├── src/                          # 源代码
│   ├── lgb2sql.py               # 树转SQL核心（CASE WHEN递归生成）
│   ├── lgb_feature_extractor.py # 模型变量提取器（统一接口）
│   ├── pipeline.py              # 旧版Pipeline入口（兼容保留）
│   │
│   ├── metadata/                # 元数据包（P4重构：Facade + 3子组件）
│   │   ├── __init__.py          # 包导出：MetadataManager, VariableClassifier, ...
│   │   ├── models.py            # VariableMetadata, TableMetadata 数据模型
│   │   ├── manager.py           # MetadataManager（Facade：加载/查询/分组/检测/统计）
│   │   ├── variable_classifier.py   # VariableClassifier（变量分类/歧义解析）
│   │   ├── override_applier.py      # OverrideApplier（变量覆盖应用）
│   │   ├── metadata_statistics.py   # MetadataStatistics（统计报告生成）
│   │   ├── classifier.py        # 表名自动分类规则
│   │   ├── key_inference.py     # 关联键推断
│   │   └── converter.py         # CSV → YAML 转换器
│   │
│   ├── core/                    # 核心功能包（SQL生成）
│   │   ├── __init__.py
│   │   ├── models.py            # 数据模型（TableGroup, JoinPlan, OutputConfig）
│   │   ├── join_planner.py      # JOIN策略规划器（表分组/桥接键/均衡分配）
│   │   │
│   │   ├── sql_builder.py       # SQLBuilder（Facade：CTE/临时表风格）
│   │   │   P1重构：~320行（原1295行），委托5个子组件
│   │   ├── sql/                 # SQL构建子模块（P1重构提取）
│   │   │   ├── __init__.py      # 包导出：5个SQL组件类
│   │   │   ├── field_collector.py      # FieldCollector（SELECT字段/列名映射）
│   │   │   ├── subquery_builder.py     # SubqueryBuilder（单表/多表/CTE/ON条件）
│   │   │   ├── credit_group_handler.py # CreditGroupHandler（征信分组/桥接表）
│   │   │   ├── merge_table_builder.py  # MergeTableBuilder（组内合并表SQL）
│   │   │   └── sql_formatter.py        # SQLFormatter（最终SQL组装/缩进/输出）
│   │   │
│   │   ├── config_loader.py     # 配置加载器（Facade，P3重构：~275行，原891行）
│   │   ├── config/              # 配置子模块（P3重构提取）
│   │   │   ├── __init__.py      # 包导出：6个配置子类
│   │   │   ├── project_config.py        # ProjectConfig（项目信息+命名工具）
│   │   │   ├── sql_generation_config.py # SQLGenerationConfig（SQL参数+JOIN策略+分区）
│   │   │   ├── output_config.py         # OutputConfig（输出表+样本表配置）
│   │   │   ├── pipeline_config.py       # PipelineConfig（流水线执行配置）
│   │   │   ├── override_config.py       # OverrideConfig（覆盖+别名+黑名单）
│   │   │   └── credit_bridge_config.py  # CreditBridgeConfig（征信桥接配置）
│   │   │
│   │   └── lgb_feature_extractor.py  # 模型变量提取器
│   │
│   ├── model_loaders/           # 模型加载器包
│   │   ├── __init__.py          # load_model() 自动选择
│   │   ├── base.py              # BaseModelLoader 基类
│   │   ├── pkl_loader.py        # PKL格式加载器
│   │   ├── pmml_loader.py       # PMML格式加载器
│   │   └── text_loader.py       # 文本格式(.model)加载器
│   │
│   ├── pipeline_pkg/            # 任务流包（一站式接口，P2重构）
│   │   ├── __init__.py          # 包导出：LgbToSqlPipeline, ScoreGenerator, ...
│   │   ├── pipeline_core.py     # LgbToSqlPipeline（Facade：~280行，原661行）
│   │   ├── feature_reporter.py  # FeatureReporter 变量元数据报告（控制台）
│   │   ├── markdown_reporter.py # MarkdownReporter Markdown格式报告
│   │   ├── scorer.py            # ScoreGenerator 打分SQL生成
│   │   ├── score_templates.py   # 打分SQL模板
│   │   └── stages/              # Pipeline Stage子模块（P2重构提取）
│   │       ├── __init__.py      # 包导出：6个Stage类
│   │       ├── context.py       # PipelineContext（流水线上下文数据容器）
│   │       ├── config_stage.py      # ConfigStage（初始化配置/元数据/组件）
│   │       ├── feature_stage.py     # FeatureExtractionStage（解析模型/提取变量）
│   │       ├── metadata_stage.py    # MetadataReportStage（查询元数据/生成报告）
│   │       ├── sql_stage.py         # SQLGenerationStage（生成JOIN SQL）
│   │       └── score_stage.py       # ScoreGenerationStage（生成打分SQL）
│   │
│   ├── tools/                   # 工具模块
│   │   ├── sql_validator.py     # SQL验证SQL生成器（9维度数据质量校验）
│   │   ├── analyze_keys.py      # 表关联键分析工具
│   │   └── excel_to_yaml.py     # Excel数据字典转YAML
│   │
│   └── utils/                   # 通用工具
│       └── (辅助函数)
│
├── config/                       # 配置文件
│   ├── config.yaml              # 主配置文件
│   ├── metadata.yaml            # 变量元数据
│   ├── metadata.pkl             # 自动生成的元数据缓存（pickle二进制）
│   └── models/                  # 模型专属配置
│       ├── MYJBV4_ZY.yaml
│       ├── JDJT_GKB.yaml
│       ├── MTSHF_DQ_FUZHAI.yaml
│       └── ZJFXJ_ZYB.yaml
│
├── data/                         # 数据文件
│   ├── 禁用变量清单.txt           # 全局禁用变量清单（供 blacklist_file 加载）
│   └── 特征映射表_新底座_*.csv   # 特征映射表
│
├── scripts/                      # 分析工具脚本
│   ├── convert_csv_to_metadata.py  # CSV→YAML转换脚本
│   ├── analysis_toolkit.py      # 统一分析工具
│   ├── get_external_tables.py   # 外部表获取脚本
│   ├── update_credit_partition.py # 征信分区更新脚本
│   ├── table_keys_edit.csv      # 表关联键编辑配置
│   ├── README.md                # 脚本使用说明
│   ├── analysis/                # 分析脚本目录
│   │   ├── analyze_behavior_ambiguous.py
│   │   └── ...
│   ├── convert/                 # 转换脚本目录
│   │   └── ...
│   └── validation/              # 验证脚本目录
│       └── generate_validation_sql.py  # SQL验证脚本生成器
│
├── docs/                       # 文档目录
│   ├── 01_usage_guide.md        # 使用指南
│   ├── 02_configuration_guide.md # 配置详解
│   ├── 03_implementation_guide.md # 实现指南
│   └── 04_faq_and_notes.md      # FAQ与注意事项
│
├── tests/                        # 测试目录
│   ├── test_all.py              # 统一测试入口（24个单元测试）
│   ├── test_regression.py       # 回归测试（4个模型全量测试）
│   ├── test_sql_validator.py    # SQL验证工具单元测试
│   └── ...                      # 其他专项测试（30+个）
│
├── requirements.txt              # 依赖包
├── run_full_pipeline.py          # 一键执行入口
└── README.md                     # 项目说明
```

> **重构说明（P0-P4）**：项目采用 **Facade + Composition** 架构模式。每个核心模块（config_loader、sql_builder、pipeline_core、metadata/manager）保留为轻量级 Facade，具体职责委托给专注的子组件。各 Facade 向下编排、向上提供统一接口，无向后兼容层。详见下方"模块职责"。

---

## 系统架构与设计

# lgb2sql 架构设计文档

## 1. 整体架构（P0-P4重构后：Facade + Composition）

```
┌─────────────────────────────────────────────────────────────────┐
│                          输入层 (Input)                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ 模型文件      │  │ 变量元数据    │  │ 配置文件             │  │
│  │ (.pkl/.pmml) │  │ (.yaml/.csv) │  │ (config.yaml)        │  │
│  │ (.model)     │  │              │  │                      │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────────┼────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      处理层 (Processing)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ model_loaders   │  │ metadata        │  │ core.config │ │
│  │ 包              │  │ 包              │  │ 包          │ │
│  │                 │  │ ┌───────────┐   │  │ ┌─────────┐ │ │
│  │ load_model()    │  │ │ Manager   │   │  │ │SQLConfig│ │ │
│  │ (自动选择)      │  │ │ (Facade)  │   │  │ │(Facade) │ │ │
│  └────────┬────────┘  │ └─────┬─────┘   │  │ └────┬────┘ │ │
│           │           │   ┌───┴───┐     │  │  ┌───┴───┐  │ │
│           │           │   ▼       ▼     │  │  ▼   ▼   ▼  │ │
│           │           │  Class.  Over.  │  │ Proj SQL  Out│ │
│           │           │  (分类)  (覆盖) │  │ Conf Conf Conf│ │
│           │           │                 │  │ ┌──────────┐ │ │
│           │           │   ┌───────────┐ │  │ │Pipeline  │ │ │
│           │           │   ▼           ▼ │  │ │Override  │ │ │
│           │           │  Stats.        │  │ │Credit    │ │ │
│           │           │  (统计)        │  │ │Bridge    │ │ │
│           │           └─────────────────┘  └─────────────┘ │
│           │                      │                │         │
│           └──────────────────────┼────────────────┘         │
│                                  │                          │
│                                  ▼                          │
│                    ┌─────────────────────────┐              │
│                    │ pipeline_pkg            │              │
│                    │ LgbToSqlPipeline        │              │
│                    │ (Facade)                │              │
│                    └───────────┬─────────────┘              │
│                        ┌───────┴───────┐                    │
│                        ▼   ▼   ▼   ▼   ▼                    │
│                      Config Feature Meta SQL Score           │
│                      Stage  Stage  Stage Stage Stage          │
│                        │     │     │    │    │              │
│                        │     │     │    │    │              │
│                        └─────┴─────┴────┴────┘              │
│                                  │                          │
│                                  ▼                          │
│                    ┌─────────────────────────┐              │
│                    │ core.sql_builder        │              │
│                    │ SQLBuilder (Facade)     │              │
│                    └───────────┬─────────────┘              │
│                        ┌───────┼───────┐                    │
│                        ▼       ▼       ▼                    │
│                      Field  Subquery  Credit                │
│                      Coll.   Builder   Group                │
│                        │       │       │                    │
│                        │    ┌──┴──┐    │                    │
│                        │    ▼     ▼    │                    │
│                        │  Merge  SQL   │                    │
│                        │  Table  Fmt   │                    │
│                        │  Builder      │                    │
│                        └─────┴────┴────┘                    │
│                                  │                          │
│                                  ▼                          │
│                    ┌─────────────────────────┐              │
│                    │ pipeline_pkg.scorer     │              │
│                    │ ScoreGenerator          │              │
│                    │ (空值→打分→评分卡)     │              │
│                    └─────────────────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                       输出层 (Output)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Hive SQL 脚本 (.sql)                   │   │
│  │              Markdown 报告 (.md)                    │   │
│  │                                                     │   │
│  │  CREATE TABLE tmp_变量拼接 AS ...                   │   │
│  │  CREATE TABLE tmp_打分结果 AS ...                   │   │
│  │  CREATE TABLE tmp_评分卡 AS ...                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 2. 模块职责

### 2.1 model_loaders 包
- **职责**：加载LightGBM模型，提取入模变量
- **输入**：`.pkl` / `.pmml` / `.model` 模型文件
- **输出**：变量名列表
- **关键类**：`BaseModelLoader`, `PklModelLoader`, `PmmlModelLoader`, `TextModelLoader`
- **入口函数**：`load_model(path)` 根据后缀自动选择加载器

### 2.2 core.config 包（P3重构：配置子模块）

采用 **Facade + 6个子配置类** 架构，`SQLConfig` 作为统一门面：

| 类 | 文件 | 职责 |
|---|------|------|
| `SQLConfig` | `config_loader.py` | Facade：统一配置入口，委托6个子配置类 |
| `ProjectConfig` | `config/project_config.py` | 项目信息（work_no/model_id）+ 命名工具（临时表名生成） |
| `SQLGenerationConfig` | `config/sql_generation_config.py` | SQL生成参数、JOIN策略、分区控制策略 |
| `OutputConfig` | `config/output_config.py` | 输出表配置、样本表字段、变量输出控制 |
| `PipelineConfig` | `config/pipeline_config.py` | 流水线执行模式、SQL保存路径、报告配置 |
| `OverrideConfig` | `config/override_config.py` | 变量覆盖、别名映射、黑名单合并 |
| `CreditBridgeConfig` | `config/credit_bridge_config.py` | 征信桥接表配置解析 |

- **黑名单加载机制**：
  1. 读取 `blacklist_file` 配置（外部清单文件路径）
  2. 逐行解析文件内容（忽略空行和注释），加载为变量名列表
  3. 与 `blacklist_vars`（YAML 内联配置）合并去重
  4. 最终黑名单 = `blacklist_vars` + `blacklist_file` 内容

### 2.3 metadata 包（P4重构：元数据子模块）

采用 **Facade + 3个子组件** 架构，`MetadataManager` 作为统一门面：

| 类 | 文件 | 职责 |
|---|------|------|
| `MetadataManager` | `manager.py` | Facade：元数据加载、查询、分组、检测、统计（~304行，原687行） |
| `VariableClassifier` | `variable_classifier.py` | 变量分类、歧义解析、平台优先级选择 |
| `OverrideApplier` | `override_applier.py` | 变量覆盖配置应用、表关联键覆盖 |
| `MetadataStatistics` | `metadata_statistics.py` | 元数据统计报告生成（平台分布、完整性等） |

- **关键数据模型**：`VariableMetadata`, `TableMetadata`（`metadata/models.py`）
- **缓存机制**：首次加载 YAML 后自动生成 `.pkl` 缓存，后续加载从缓存读取（速度提升约90倍），YAML 修改后自动失效重建

### 2.4 core 包（SQL生成核心，P1重构）

#### models.py
- **职责**：定义SQL生成的核心数据结构
- **关键类**：
  - `TableGroup`: 临时表分组（同platform+join_key的表集合）
  - `JoinPlan`: JOIN执行计划（样本表+分组列表+桥接键）
  - `OutputConfig`: 输出表配置（表名/数据库/分区/空值填充）

#### join_planner.py
- **职责**：JOIN策略规划，将变量按(platform, join_key)分组
- **关键方法**：
  - `plan()`: 规划JOIN策略，生成JoinPlan
  - `_split_tables()`: 按策略拆分表组（sequential/balanced）
  - `_resolve_ambiguous_variables()`: 解析歧义变量
- **子组拆分策略**：
  - `sequential`: 顺序切分（先装满第一组）
  - `balanced`: 均衡分配（默认，让每组子查询数量接近）

#### sql_builder.py（P1重构：SQL构建Facade）

采用 **Facade + 5个SQL子组件** 架构（~320行，原1295行）：

| 类 | 文件 | 职责 |
|---|------|------|
| `SQLBuilder` | `sql_builder.py` | Facade：SQL编排入口，提供 `build_cte_sql()` / `build_temp_table_sql()` |
| `FieldCollector` | `sql/field_collector.py` | SELECT字段收集、变量→列名映射、平台分类 |
| `SubqueryBuilder` | `sql/subquery_builder.py` | 单表/多表子查询、ON条件构建、CTE构造 |
| `CreditGroupHandler` | `sql/credit_group_handler.py` | 征信组检测、桥接表SQL、征信临时表生成 |
| `MergeTableBuilder` | `sql/merge_table_builder.py` | 组合并表SQL、merge table映射 |
| `SQLFormatter` | `sql/sql_formatter.py` | 最终SELECT/JOIN组装、缩进、文件输出、执行摘要 |

**Facade保留的核心编排逻辑**：
- `_build_group_temp_table()`: 分组临时表生成（含去重处理）
- `_build_non_credit_group_temp_table()`: 非征信分组临时表

### 2.5 pipeline_pkg 包（P2重构：Pipeline Stage子模块）

采用 **Facade + 5个Stage类** 架构，`LgbToSqlPipeline` 作为统一门面（~280行，原661行）：

| 类 | 文件 | 职责 |
|---|------|------|
| `LgbToSqlPipeline` | `pipeline_core.py` | Facade：完整任务流编排（配置→解析→报告→SQL→打分） |
| `PipelineContext` | `stages/context.py` | 流水线上下文数据容器（跨Stage共享状态） |
| `ConfigStage` | `stages/config_stage.py` | 初始化配置、元数据、模型加载器 |
| `FeatureExtractionStage` | `stages/feature_stage.py` | 解析模型文件，提取入模变量 |
| `MetadataReportStage` | `stages/metadata_stage.py` | 查询变量元数据，生成命中报告 |
| `SQLGenerationStage` | `stages/sql_stage.py` | 生成JOIN SQL（调用SQLBuilder） |
| `ScoreGenerationStage` | `stages/score_stage.py` | 生成打分SQL（调用ScoreGenerator） |

### 2.6 scorer.py（打分引擎）
- **职责**：评分卡映射和分箱
- **关键类**：`ScoreGenerator`
- **公式**：`score = A - B * ln(odds)`
- **处理步骤**：空值填充（NVL）→ 全空标记（all_null_flag）→ sigmoid概率 → 评分卡映射

### 2.7 tools 包
- **职责**：辅助工具
- **关键类**：`SqlValidator`（9维度数据质量校验SQL生成器）

### 2.8 utils/excel_to_yaml.py
- **职责**：Excel数据字典转YAML
- **输入**：Excel文件（字段名、含义、来源表、表描述）
- **输出**：YAML元数据文件

## 3. 数据流

```
模型文件 ──► model_loaders ──► 变量列表
                                    │
                                    ▼
元数据文件 ──► metadata.Manager ──► 变量映射表
   │              (Facade)              │
   │    ┌────────┴────────┐            │
   │    ▼                 ▼            │
   └► VariableClassifier  OverrideApplier
                                    │
                                    ▼
配置文件 ──► core.config.SQLConfig ──► 样本表/输出表配置
   │              (Facade)              │
   │    ┌────────┴────────┐            │
   │    ▼                 ▼            │
   └► ProjectConfig  SQLGenerationConfig
                                    │
                                    ▼
                        pipeline_pkg.LgbToSqlPipeline
                              (Facade)
                                    │
              ┌─────────┬──────────┼──────────┬─────────┐
              ▼         ▼          ▼          ▼         ▼
        ConfigStage  FeatureStage  MetadataStage  SQLStage  ScoreStage
              │         │          │          │         │
              │         │          │          ▼         │
              │         │          │    core.sql_builder│
              │         │          │       (Facade)     │
              │         │          │    ┌───┴───┴───┐   │
              │         │          │    ▼   ▼   ▼   ▼   │
              │         │          │  Field Subq  Cred  Merge Fmt
              │         │          │  Coll  Builder Group Build  |
              │         │          │                        Formatter
              │         │          │          │         │
              └─────────┴──────────┴──────────┴─────────┘
                                    │
                                    ▼
                              完整SQL脚本
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              变量拼接SQL      打分SQL          报告文件
              (JOIN/CTE)    (评分卡映射)       (.md/.sql)
```

## 4. 接口定义

### 4.1 输入接口

```python
# 模型输入
model_path: str              # .pkl / .pmml / .model 文件路径

# 元数据输入
metadata_path: str           # .yaml 或 .json 文件路径

# 配置输入（通过 SQLConfig Facade）
config_path: str             # config.yaml 路径
```

### 4.2 输出接口

```python
# Pipeline 输出
result: {
    'features': List[str],       # 入模变量列表
    'join_sql': str,             # 变量拼接SQL
    'score_sql': str,            # 打分SQL（如启用）
    'report': str                # Markdown报告
}

# SQL文件输出
output_sql_path: str          # .sql 文件保存路径
output_report_path: str       # .md 报告保存路径
```

## 5. 扩展点

1. **新模型格式支持**：在 `model_loaders/` 包中继承 `BaseModelLoader` 添加新的加载器
2. **新SQL方言**：在 `core/sql/` 子模块中扩展 `SQLFormatter` 支持不同数据库方言
3. **新配置项**：在 `core/config/` 子模块中添加新的配置子类，并在 `SQLConfig` Facade中注册
4. **新数据源**：在 `utils/excel_to_yaml.py` 中支持更多输入格式
5. **新Pipeline Stage**：在 `pipeline_pkg/stages/` 中继承基类添加新的处理阶段
6. **新元数据处理**：在 `metadata/` 包中添加新的分析组件，并在 `MetadataManager` 中集成


---

## 模块详细说明

### 核心组件速查

| 组件/函数 | 文件 | 说明 |
|-----------|------|------|
| `LgbToSqlPipeline` | `pipeline_pkg/pipeline_core.py` | Pipeline Facade：完整任务流编排 |
| `SQLBuilder` | `core/sql_builder.py` | SQL构建 Facade：CTE/临时表SQL生成 |
| `SQLConfig` | `core/config_loader.py` | 配置 Facade：统一配置入口 |
| `MetadataManager` | `metadata/manager.py` | 元数据 Facade：加载/查询/分组/检测/统计 |
| `MarkdownReporter` | `pipeline_pkg/markdown_reporter.py` | Markdown格式报告：生成结构化的变量分析报告 |
| `ScoreGenerator` | `pipeline_pkg/scorer.py` | 打分SQL生成：空值填充→打分→评分卡 |
| `SqlValidator` | `tools/sql_validator.py` | SQL验证SQL生成器：9维度数据质量校验SQL自动生成 |
| `run_pipeline()` | `pipeline_pkg/pipeline_core.py` | 便捷函数，一键执行 |

### model_loaders 包

| 类/函数 | 说明 |
|---------|------|
| `load_model(path)` | 根据后缀自动选择加载器 |
| `PklModelLoader` | 加载 `.pkl` 格式（支持pickle/joblib回退） |
| `PmmlModelLoader` | 加载 `.pmml` 格式（内置XML解析，无需pypmml） |
| `TextModelLoader` | 加载 `.model` 格式（纯文本解析，无lightgbm依赖） |

### metadata 包（P4重构：Facade + 3子组件）

| 类/函数 | 文件 | 说明 |
|---------|------|------|
| `MetadataManager` | `metadata/manager.py` | Facade：元数据加载、查询、分组、检测、统计报告（~304行，支持自动pickle缓存加速） |
| `VariableClassifier` | `metadata/variable_classifier.py` | 变量分类、歧义解析、平台优先级选择 |
| `OverrideApplier` | `metadata/override_applier.py` | 变量覆盖配置应用、表关联键覆盖 |
| `MetadataStatistics` | `metadata/metadata_statistics.py` | 元数据统计报告生成（平台分布、完整性、特殊变量检测） |
| `VariableMetadata` | `metadata/models.py` | 单变量元数据（名称、表、分类、关联键等） |
| `TableMetadata` | `metadata/models.py` | 单表元数据（表名、分类、变量列表等） |
| `classify_category()` | `metadata/classifier.py` | 根据表名推断变量分类 |
| `infer_join_keys()` | `metadata/key_inference.py` | 根据表名和分类推断关联键 |
| `convert_csv_to_yaml()` | `metadata/converter.py` | CSV特征映射表转YAML元数据 |
| `get_statistics()` | `metadata/manager.py` | 获取元数据详细统计字典 |
| `print_statistics()` | `metadata/manager.py` | 打印元数据统计报告到控制台 |
| `get_statistics_json()` | `metadata/manager.py` | 导出统计信息为JSON字符串 |

### core 包（SQL生成，P1重构：Facade + 5子组件）

| 类/函数 | 文件 | 说明 |
|---------|------|------|
| `TableGroup` | `core/models.py` | 临时表分组（同platform+join_key的表集合） |
| `JoinPlan` | `core/models.py` | JOIN执行计划 |
| `OutputConfig` | `core/models.py` | 输出表配置 |
| `JoinPlanner` | `core/join_planner.py` | JOIN策略规划：按(platform, join_key)分组，支持balanced/sequential拆分策略 |
| `SQLBuilder` | `core/sql_builder.py` | SQL构建 Facade：~320行（原1295行），生成CTE或临时表风格的完整SQL |
| `FieldCollector` | `core/sql/field_collector.py` | SELECT字段收集、变量→数据库列名映射、平台分类 |
| `SubqueryBuilder` | `core/sql/subquery_builder.py` | 单表/多表子查询、ON条件构建、CTE构造 |
| `CreditGroupHandler` | `core/sql/credit_group_handler.py` | 征信组检测、桥接表SQL生成、征信临时表构建 |
| `MergeTableBuilder` | `core/sql/merge_table_builder.py` | 组合并表SQL、merge table映射生成 |
| `SQLFormatter` | `core/sql/sql_formatter.py` | 最终SELECT/JOIN组装、SQL缩进、文件保存、执行摘要 |

### core.config 包（P3重构：配置子模块）

| 类/函数 | 文件 | 说明 |
|---------|------|------|
| `SQLConfig` | `core/config_loader.py` | 配置 Facade：~275行（原891行），统一配置入口 |
| `ProjectConfig` | `core/config/project_config.py` | 项目信息 + 临时表命名工具 |
| `SQLGenerationConfig` | `core/config/sql_generation_config.py` | SQL生成参数、JOIN策略、分区控制 |
| `OutputConfig` | `core/config/output_config.py` | 输出表配置、样本表字段、变量输出控制 |
| `PipelineConfig` | `core/config/pipeline_config.py` | 流水线执行模式、SQL保存路径 |
| `OverrideConfig` | `core/config/override_config.py` | 变量覆盖、别名映射、黑名单合并 |
| `CreditBridgeConfig` | `core/config/credit_bridge_config.py` | 征信桥接表配置解析 |

### pipeline_pkg 包（P2重构：Facade + 5 Stage类）

| 类/函数 | 文件 | 说明 |
|---------|------|------|
| `LgbToSqlPipeline` | `pipeline_pkg/pipeline_core.py` | Pipeline Facade：~280行（原661行），完整任务流编排：配置→解析→报告→SQL→打分 |
| `PipelineContext` | `pipeline_pkg/stages/context.py` | 流水线上下文数据容器（跨Stage共享状态） |
| `ConfigStage` | `pipeline_pkg/stages/config_stage.py` | 初始化配置、元数据、模型加载器 |
| `FeatureExtractionStage` | `pipeline_pkg/stages/feature_stage.py` | 解析模型文件，提取入模变量 |
| `MetadataReportStage` | `pipeline_pkg/stages/metadata_stage.py` | 查询变量元数据，生成命中报告 |
| `SQLGenerationStage` | `pipeline_pkg/stages/sql_stage.py` | 生成JOIN SQL（调用SQLBuilder Facade） |
| `ScoreGenerationStage` | `pipeline_pkg/stages/score_stage.py` | 生成打分SQL（调用ScoreGenerator） |

### tools 包

| 类/函数 | 文件 | 说明 |
|---------|------|------|
| `SqlValidator` | `sql_validator.py` | SQL验证SQL生成器：自动生成9维度数据质量校验SQL |
| `generate_sample_count_sql()` | `sql_validator.py` | 样本量一致性校验SQL |
| `generate_missing_rate_sql()` | `sql_validator.py` | 变量缺失率统计SQL |
| `generate_high_missing_sql()` | `sql_validator.py` | 高缺失率变量汇总SQL（LATERAL VIEW EXPLODE） |
| `generate_distribution_sql()` | `sql_validator.py` | 数据分布统计SQL（均值/标准差/分位数） |
| `generate_mom_change_sql()` | `sql_validator.py` | 环比波动检测SQL |
| `generate_pk_uniqueness_sql()` | `sql_validator.py` | 主键唯一性校验SQL |
| `generate_score_distribution_sql()` | `sql_validator.py` | 评分分布统计SQL |
| `generate_score_bucket_sql()` | `sql_validator.py` | 评分区间分布SQL（7档分箱） |
| `generate_coverage_sql()` | `sql_validator.py` | 变量有效值覆盖率SQL |
| `generate_all()` | `sql_validator.py` | 生成全部9维度验证SQL |
| `generate_markdown_report()` | `sql_validator.py` | 生成Markdown格式分析报告 |

### scripts/analysis 目录

| 脚本 | 说明 |
|------|------|
| `generate_validation_sql.py` | SQL验证脚本命令行入口，自动加载模型配置、提取变量、生成验证SQL和报告 |

---

## 控制策略详解

本章详细说明 lgb2sql 的核心控制策略，帮助用户理解每个策略的工作原理、配置方式和适用场景。

---

### 策略一：分区控制策略（partition_control）

分区控制策略决定每张变量子查询中如何限制分区字段，直接影响查询性能和数据正确性。

#### 两种策略模式

| 策略 | 生成的条件 | 适用场景 | 性能特点 |
|------|-----------|----------|----------|
| `equality`（等值） | `partition_field = '${biz_date}'` | 按日分区表（如 `dt`）、需要精确匹配业务日期 | 分区裁剪效果好，扫描数据量小 |
| `range`（范围） | `partition_field >= min_partition` | 按月分区表（如 `part_id`）、需要回溯历史数据 | 扫描数据量较大，但支持回溯 |

#### 四级优先级配置

配置支持四个层级，优先级从高到低：

```
by_table（按表） > by_platform（按平台） > by_category（按分类） > default（默认）
```

**配置示例**：

```yaml
partition_control:
  default:
    strategy: "range"
    partition_field: "dt"
    min_partition: "202401"
  by_category:
    "征信变量":
      strategy: "range"
      partition_field: "part_id"
      min_partition: "202512"
    "行为变量":
      strategy: "range"
      partition_field: "dt"
      min_partition: "202401"
  by_platform: {}
  by_table: {}
```

#### 典型场景配置

**场景1：贷前模型（按日分区）**
```yaml
partition_control:
  default:
    strategy: "equality"
        partition_field: "dt"
```
所有表按业务日期精确匹配，适合贷前申请日数据。

**场景2：贷中模型（按月分区+回溯）**
```yaml
partition_control:
  default:
    strategy: "range"
    partition_field: "part_id"
    min_partition: "202512"
  by_category:
    "行为变量":
      strategy: "range"
      partition_field: "dt"
      min_partition: "202401"
```
征信变量按月分区回溯到202512，行为变量按日分区回溯到202401。

**场景3：混合场景（等值+范围）**
```yaml
partition_control:
  default:
    strategy: "equality"
    partition_field: "dt"
  by_category:
    "征信变量":
      strategy: "range"
      partition_field: "part_id"
      min_partition: "202512"
```
默认等值匹配，征信变量单独使用范围匹配。

**场景4：按表单独配置（by_table）**
```yaml
partition_control:
  default:
    strategy: "range"
    partition_field: "dt"
    min_partition: "202401"
  by_category:
    "征信变量":
      strategy: "range"
      partition_field: "part_id"
      min_partition: "202512"
  by_table:
    "jsbrpt.v_ods_02_all_zzxqsf_md5":
      strategy: "range"
      partition_field: "part_id"
      min_partition: "202408"
```
`by_table` 优先级最高，可针对单张表设置独立的分区策略。如中征信视图表需要回溯到202408，与其他征信变量不同。

#### 注意事项

- `equality` 模式下不配置 `min_partition`
- `range` 模式下 `min_partition` 必须与分区字段格式一致（如 `part_id` 用 `"202512"`，`dt` 用 `"20240101"`）
- 当表同时配置了 `time_range_joins` 时，分区条件可能被子查询优化调整

---

### 策略二：组内合并策略（group_merge）

组内合并策略控制是否将同一分组内的多张临时表合并为一张中间总表。

#### 工作原理

当 `group_merge: true` 时：

```
合并前：
  tmp_..._pbci_part1 (10个变量)
  tmp_..._pbci_part2 (8个变量)
  tmp_..._pbci_part3 (12个变量)
  → 最终JOIN需要 3 个LEFT JOIN

合并后：
  tmp_..._pbci_part1 (10个变量)
  tmp_..._pbci_part2 (8个变量)
  tmp_..._pbci_part3 (12个变量)
  tmp_..._pbci_all (合并后的30个变量)
  → 最终JOIN只需要 1 个LEFT JOIN
```

#### 配置方式

```yaml
sql_generation:
  group_merge: true   # 启用组内合并
```

#### 适用场景

| 场景 | 建议配置 | 原因 |
|------|----------|------|
| 变量表多且分散 | `true` | 减少最终JOIN层数，提升性能 |
| 单分组内只有1-2张表 | `false` | 合并无收益，增加临时表数量 |
| 内存/临时表空间有限 | `false` | 合并会产生额外的中间表 |

---

### 策略三：征信桥接策略（credit_primary_table）

征信桥接策略解决样本表（`cert_no`）与征信变量表（`ci_rpt_id`）之间的关联问题。

#### 两级JOIN架构

```
样本表 (apply_no, cert_no, issue_time)
    ↓ JOIN (cert_no = MD5(be_qry_cert_num) + 时间窗口)
征信主键表 (ci_rpt_id, be_qry_cert_num, rpt_tm)
    ↓ JOIN (ci_rpt_id = ci_rpt_id)
征信变量表 (ci_rpt_id, var1, var2, ...)
```

#### 桥接表SQL生成逻辑

```sql
-- 步骤1：创建桥接表
DROP TABLE IF EXISTS tmp_..._pbci_bridge;
CREATE TABLE tmp_..._pbci_bridge AS
SELECT DISTINCT
    s.apply_no,
    p.ci_rpt_id
FROM sample_table s
JOIN wdyy_mrs.t_pbci_summary_other p
    ON s.cert_no = MD5(p.be_qry_cert_num)
    AND to_date(substr(p.rpt_tm, 1, 10)) <= to_date(s.issue_time)
    AND DATEDIFF(to_date(s.issue_time), to_date(substr(p.rpt_tm, 1, 10))) <= 90
WHERE p.part_id >= '202512';

-- 步骤2：征信变量子查询使用桥接表
SELECT b.apply_no, t.var1, t.var2
FROM tmp_..._pbci_bridge b
JOIN zxbl_table t ON b.ci_rpt_id = t.ci_rpt_id
WHERE t.part_id >= '202512';
```

#### 关键配置说明

| 配置项 | 作用 | 典型值 |
|--------|------|--------|
| `md5_transform` | 样本 `cert_no` 是否等于 MD5(征信表 `be_qry_cert_num`) | 消金场景通常 `true` |
| `time_window_days` | 取样本时间前多少天内的征信报告 | `90` 天 |
| `direction` | `"<="` 表示征信时间 ≤ 样本时间（申请前） | 贷前 `"<="`，贷后 `">="` |

#### 适用场景

- **贷前模型**：`direction: "<="`，取申请时间前的最新征信报告
- **贷中模型**：`direction: "<="`，取放款时间前的最新征信报告（或调整为 `">="` 取放款后）
- **回溯场景**：调整 `time_window_days` 确保能匹配到历史数据

---

### 策略四：时间区间匹配策略（time_range_joins）

时间区间匹配策略用于非等值关联场景，如取时间最近的一条记录。

#### 两种匹配模式

**模式A：range（范围匹配，默认）**

适用场景：取申请时间前90天内的最新征信报告

```sql
SELECT *
FROM (
    SELECT
        s.cert_no, t.var1,
        ROW_NUMBER() OVER (
            PARTITION BY s.cert_no
            ORDER BY t.rpt_tm DESC
        ) AS rn
    FROM sample s
    JOIN var_table t ON s.cert_no = t.cert_no
    WHERE to_date(substr(t.rpt_tm, 1, 10)) <= to_date(s.issue_time)
      AND DATEDIFF(to_date(s.issue_time), to_date(substr(t.rpt_tm, 1, 10))) <= 90
) tmp
WHERE rn = 1
```

特点：
- 子查询限制 `partition_field = '${biz_date}'`
- 使用 `ROW_NUMBER()` 去重
- 取时间最近的一条

**模式B：equality（等号匹配）**

适用场景：part_id 的上一个月等于 issue_time 的月份

```sql
SELECT s.cert_no, t.var1
FROM sample s
JOIN var_table t
    ON s.cust_id = t.cust_id
    AND to_char(TO_DATE(t.part_id::text, 'YYYYMM') + INTERVAL '1 month', 'YYYYMM')
        = to_char(TO_DATE(s.issue_time::text, 'YYYYMMdd'), 'YYYYMM')
```

特点：
- 子查询不限制 `partition_field = '${biz_date}'`
- 无需 `ROW_NUMBER()` 去重
- 跨月份精确匹配

**模式C：range + dedup + between（高级范围匹配）**

适用场景：中征信等需要按月区间匹配，且变量表存在一对多（同一证件号多条记录）

```yaml
time_range_joins:
  "jsbrpt.v_ods_02_all_zzxqsf_md5":
    match_mode: "range"
    time_field: "score_date"
    sample_time_field: "issue_time"
    time_function: "MONTHS_BETWEEN"
    window: 3
    direction: "between"
    dedup: true
    dedup_partition_by: "${sample_key}"
    dedup_order_by: "score_date DESC"
    output_time_field: "formatted_score_date"
```

生成的SQL结构：

```sql
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY t.cert_no
                ORDER BY t.score_date DESC
    ) AS rn,
    to_char(to_date(t.score_date, 'yyyyMMdd'), 'yyyy-MM-dd') AS formatted_score_date
    FROM sample s
    JOIN jsbrpt.v_ods_02_all_zzxqsf_md5 t
        ON s.cert_no = t.cert_no
        AND MONTHS_BETWEEN(
            to_date(s.issue_time, 'yyyyMMdd'),
            to_date(t.score_date, 'yyyyMMdd')
        ) BETWEEN 0 AND 3
) tmp
WHERE rn = 1
```

特点：
- `direction: "between"` 生成 `BETWEEN 0 AND {window}` 条件
- `dedup: true` 在子查询内添加 `ROW_NUMBER()` 去重
- `output_time_field` 将原始时间字段格式化后输出，供后续关联使用
- 适用于中征信等视图表（`cert_no` 直接关联，无需 `ci_rpt_id` 桥接）

#### 配置决策树

```
需要按时间窗口取最近一条？
  ├─ 是 → 使用 range 模式
  │       ├─ 按天计算窗口 → time_function: DATEDIFF
  │       ├─ 按月计算窗口 → time_function: MONTHS_BETWEEN
  │       │   ├─ 单向区间（如3个月前） → direction: "<=" 或 ">="
  │       │   └─ 双向区间（如0-3个月内） → direction: "between"
  │       └─ 变量表一对多 → dedup: true
  └─ 否 → 使用 equality 模式
          └─ 配置 time_expr 和 sample_expr 实现等式两边对齐
```

---

### 策略五：自定义JOIN条件策略（custom_join_conditions）

自定义JOIN条件策略用于处理标准等值关联无法满足的复杂关联场景。

#### 支持的三类自定义

**类型1：MD5转换关联**

场景：样本表的 `cert_no` 是 MD5 加密后的值，变量表存储的是明文。

```yaml
custom_join_conditions:
  by_table:
    "ads.ads_risk_$platform_cust_dz_indicator_ss":
      join_key: "cert_no"
      sample_key: "cert_no"
      md5_transform: true
```

生成的条件：`s.cert_no = MD5(t.cert_no)`

**类型2：时间偏移关联**

场景：申请时间需要减2天才能匹配到T+1更新的数据。

```yaml
custom_join_conditions:
  by_table:
    "ads.ads_risk_$platform_cust_dz_indicator_ss":
      join_key: "cert_no"
      time_offset:
        field: "issue_time"
        offset_days: -2
        target_field: "data_dt"
        target_expr: "cast(to_char(to_date({field}, 'yyyyMMdd') - 2, 'yyyyMMdd') AS int)"
```

生成的条件：`t.data_dt = cast(to_char(to_date(s.issue_time, 'yyyyMMdd') - 2, 'yyyyMMdd') AS int)`

**类型3：完全自定义ON条件**

场景：关联逻辑过于复杂，需要完全手写ON条件。

```yaml
custom_join_conditions:
  by_table:
    "some_complex_table":
      custom_on_clause: "s.apply_no = t.apply_no AND s.dt = t.data_dt AND t.status = 'ACTIVE'"
```

#### 优先级规则

```
custom_join_conditions.by_table > table_join_keys > metadata.yaml 默认值
```

---

### 策略六：额外WHERE条件策略（extra_where_conditions）

额外WHERE条件策略用于在标准分区条件之外，为特定表添加业务过滤条件。

#### 三级优先级

```
by_table（按表） > by_platform（按平台） > by_category（按分类）
```

#### 典型应用场景

**场景1：限定产品类型**
```yaml
extra_where_conditions:
  by_table:
    "wdyy_mrs.T_CC_Cust_Crdt_Info_Stats":
      - "prd_sub_cls_cd IN ('MYJBV4')"
```
只取借呗V4产品的数据，避免其他产品数据干扰。

**场景2：限定时间范围**
```yaml
extra_where_conditions:
  by_table:
    "wdyy_mrs.T_CC_Cust_Crdt_Info_Stats":
      - "part_id >= 202602"
```
在 `partition_control` 的 `min_partition` 基础上进一步限制。

**场景3：排除NULL值**
```yaml
extra_where_conditions:
  by_category:
    "行为变量":
      - "prd_sub_cls_cd IS NOT NULL"
```
为所有行为变量表添加非空过滤。

#### 与 partition_control 的区别

| 特性 | `partition_control` | `extra_where_conditions` |
|------|---------------------|--------------------------|
| 作用 | 控制分区扫描范围 | 添加业务过滤条件 |
| 生成位置 | 子查询的WHERE子句 | 子查询的WHERE子句 |
| 条件类型 | 分区字段条件 | 任意字段条件 |
| 典型值 | `dt = '${biz_date}'` | `prd_sub_cls_cd IN ('MYJBV4')` |

---

### 策略七：歧义变量解析策略（platform + behavior_platform_priority）

当一个变量名存在于多张表时（歧义），系统按以下策略选择：

#### 解析流程

```
1. 收集变量匹配到的所有候选表
2. 检查是否配置了 variable_overrides
   ├─ 是 → 使用覆盖配置的表
   └─ 否 → 继续
3. 检查 platform 配置是否匹配某张表的平台
   ├─ 是 → 选择该平台下的表
   └─ 否 → 继续
4. 按 behavior_platform_priority 顺序遍历
   ├─ 找到第一个有变量命中的平台 → 选择该平台下的表
   └─ 未找到 → 使用第一个候选表
```

#### 配置影响

| 配置项 | 影响 |
|--------|------|
| `platform` | 直接指定歧义变量的首选平台 |
| `platform_value` | 影响 `$platform` 占位符的替换值，进而影响表名匹配 |
| `behavior_platform_priority` | 当 `platform` 不匹配时的 fallback 顺序 |

#### 示例

假设变量 `cust_age` 同时存在于：
- `行为变量-总行`.`T_CC_Cust_Info`（平台：行为变量-总行）
- `行为变量-消金`.`T_CCRDYYF_Cust_Info`（平台：行为变量-消金）

配置1：
```yaml
platform: "行为变量-消金"
```
→ 选择 `T_CCRDYYF_Cust_Info`

配置2：
```yaml
platform: ""
behavior_platform_priority:
  - "行为变量-总行"
  - "行为变量-消金"
```
→ 选择 `T_CC_Cust_Info`（总行优先）

---

### 策略八：IN子查询优化策略

在变量子查询中，使用 `IN` 条件限制关联键的范围，避免全表扫描。



```sql
SELECT t.apply_no, t.var1
FROM edap.v_BRDT_APPLYLOANSTR_md5 t
WHERE t.dt = '${biz_date}'          -- 限制分区
  AND t.apply_no IN (
      SELECT apply_no FROM sample   
  )
```

#### 适用场景

- 样本表包含多个 `dt` 分区的回溯数据
- 变量表只需要匹配最新业务日期的数据
- 需要保证样本完整性，不因为 `dt` 不匹配而丢失数据

---

### 策略九：临时表拆分策略（max_subquery_join）

临时表拆分策略控制单张临时表内最多容纳多少个子查询JOIN，超过则拆分为多张临时表。

#### 工作原理

```
假设某平台有 10 张变量表，max_subquery_join = 4

拆分结果：
  tmp_..._wd_001: 包含表1-4的JOIN（4个子查询）
  tmp_..._wd_002: 包含表5-8的JOIN（4个子查询）
  tmp_..._wd_003: 包含表9-10的JOIN（2个子查询）

最终输出：
  LEFT JOIN tmp_..._wd_001 ON ...
  LEFT JOIN tmp_..._wd_002 ON ...
  LEFT JOIN tmp_..._wd_003 ON ...
```

#### 配置建议

| 场景 | 建议值 | 原因 |
|------|--------|------|
| 变量分散在大量表中 | 3-4 | 避免单表JOIN过多导致性能下降 |
| 变量集中在少量表中 | 5-6 | 减少临时表数量，降低管理复杂度 |
| 单表变量极多（>50个） | 2-3 | 单个子查询可能很长，需要控制 |

#### 与 group_merge 的协同

当 `group_merge: true` 时：
- 先按 `max_subquery_join` 拆分为多个part临时表
- 再将所有part临时表合并为一个总临时表
- 最终输出只需要JOIN总临时表

---

### 策略组合示例

以下是一个完整的贷中模型配置，展示了多策略的组合使用：

```yaml
# 1. 项目信息
project:
  work_no: "01011939"
  model_id: "MYJBV4_DZZY"

# 2. 平台配置（贷中字节模型）
platform: "字节"
platform_value: "dyf"

# 3. 样本表（贷中样本含 cert_no 和 issue_time）
sample:
  table_name: tmp_01011939_20260421_myjbv4_dz_sample
  key: apply_no
  fields: [apply_no, cust_id, cert_no, issue_time]

# 4. SQL生成参数
sql_generation:
  max_subquery_join: 4
  group_merge: true
  partition_control:
    default:
      strategy: "range"
      partition_field: "dt"
      min_partition: "202401"
    by_category:
      "征信变量":
        strategy: "range"
        partition_field: "part_id"
        min_partition: "202512"

# 5. 征信桥接（取申请前90天内的征信报告）
credit_primary_table:
  enabled: true
  time_window_days: 90
  md5_transform: true
  direction: "<="

# 6. 自定义JOIN（贷中行为变量MD5+时间偏移）
custom_join_conditions:
  by_table:
    "ads.ads_risk_$platform_cust_dz_indicator_ss":
      md5_transform: true
      time_offset:
        offset_days: -2

# 7. 额外WHERE条件（限定产品类型）
extra_where_conditions:
  by_table:
    "wdyy_mrs.T_CC_Cust_Crdt_Info_Stats":
      - "prd_sub_cls_cd IN ('MYJBV4')"
```
