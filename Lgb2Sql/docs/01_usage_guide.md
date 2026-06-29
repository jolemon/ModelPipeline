# lgb2sql 使用指南

> 本文档包含项目简介、功能特性、项目结构、快速开始和完整使用案例。

---

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [完整使用案例](#完整使用案例)
- [回归测试](#案例七回归测试)

---

## 项目简介

`lgb2sql` 是一个自动化工具，用于将 LightGBM 模型的入模变量列表转换为 Hive SQL 变量拼接脚本，解决大数据风控场景中多变量表关联取数的重复开发问题。

在风控模型开发中，一个模型往往涉及数十甚至上百张变量表的关联取数。传统方式需要开发工程师手动编写每张表的子查询、处理重复字段、统一关联键、合并临时表，耗时且容易出错。lgb2sql 通过解析模型文件自动提取入模变量，结合预定义的变量元数据，自动生成完整的Hive SQL拼接脚本，将开发时间从数小时缩短至数分钟。

## 功能特性

### 核心功能

1. **多格式模型解析**：支持 `.pkl` (pickle/joblib)、`.pmml`、`.model` (LightGBM文本格式) 三种模型格式
2. **智能元数据管理**：
- YAML/JSON 格式管理变量元数据（表名、分类、关联键、分区字段等）
- 自动分类（征信/行为/外数/模型分）
- 自动推断关联键
- 跨表重复变量检测
3. **SQL自动生成**：
- 按变量来源表生成子查询
- 按 (平台, 关联键) 细粒度分组合并临时表
- 自动处理组内重复字段（添加表别名前缀）
- 支持 CTE(WITH) 和临时表两种风格
- 超过 `max_subquery_join` 自动拆分
4. **变量覆盖配置**：通过 `variable_overrides` 处理异常变量（未命中/歧义）
5. **模型打分SQL**：
- 空值填充（NVL → -999999）
- 全空样本标记（`all_null_flag`）
- sigmoid 概率计算
- 评分卡映射（log-odds转换）
6. **数据字典转换**：Excel/CSV 数据字典 → YAML 元数据
7. **元数据统计报告**：一键输出元数据画像（分类/平台分布、表维度详情、完整性统计、特殊变量检测等）

### 高级特性

8. **分区控制策略** (`partition_control`)：
- `range` 策略：使用 `part_id >= min_partition` 限制分区范围，支持回溯场景
- `equality` 策略：使用 `dt = '${biz_date}'` 等值匹配
- 支持按表/分类/平台级别配置不同策略
9. **组内合并** (`group_merge`)：
- 同一分组内多张表自动合并为一张临时表
- 减少最终JOIN层数，提升查询性能
10. **时间区间匹配** (`time_range_joins`)：
- 支持 `DATEDIFF`（天数差）和 `MONTHS_BETWEEN`（月份差）两种时间函数
- 自动添加 `ROW_NUMBER()` 去重，取时间最近的一条记录
- 支持 `equality` 等号匹配模式（跨月份精确匹配）
11. **征信桥接表** (`credit_primary_table`)：
- 自动构建征信桥接表，关联样本表与征信主键表
- 支持 MD5 转换、时间窗口过滤（如90天内）
- 支持 `ci_rpt_id` 到 `cert_no` 的两级JOIN
12. **平台占位符解析** (`$platform`)：
- 表名支持 `$platform` 占位符（如 `ads.ads_risk_$platform_cust_dz_indicator_ss`）
- 根据配置自动解析为具体平台名（如 `myjb` / `dyf`）
13. **额外 WHERE 条件** (`extra_where_conditions`)：
- 支持分类/平台/表三级条件配置
- 优先级：表 > 平台 > 分类
14. **自定义 JOIN 条件** (`custom_join_conditions`)：
- 支持 MD5 转换（如 `cert_no = MD5(apply_no)`）
- 支持时间偏移关联（如申请时间减2天匹配数据日期）
- 支持自定义 ON 条件完全覆盖
15. **IN 子查询优化**：
- 变量子查询中的 `IN` 条件不再限制 `WHERE dt = '${biz_date}'`
- 支持多分区样本回溯场景
16. **Pipeline 输出改进**：
- 支持生成 Markdown 格式分析报告
- `verbose` 参数控制日志输出详细程度
17. **禁用变量黑名单** (`blacklist_vars` / `blacklist_file`)：
- 支持 YAML 内联配置和外部清单文件两种方式，合并生效
- 入模变量命中黑名单时自动告警提示
- 全局通用清单通过 `blacklist_file` 复用，模型专属变量通过 `blacklist_vars` 补充
18. **自动缓存加速**：
- 首次加载 YAML 元数据后自动生成 `.pkl` 二进制缓存
- 后续加载从缓存读取，速度提升 **~90倍**（如 51s → 0.6s）
- 缓存自动失效：YAML 文件修改后自动检测并重建缓存
- 对用户完全透明，无需任何配置
19. **SQL验证工具** (`src/tools/sql_validator.py`)：
- 自动生成9维度Hive SQL验证脚本（样本量一致性、缺失率、高缺失变量、数据波动、环比波动、主键唯一性、评分分布、评分区间、变量覆盖度）
- 支持命令行一键生成验证SQL和分析报告
- 生成的SQL可直接在Hive/Spark中执行，输出Markdown格式分析报告

---

## 快速开始

以下内容均可以请智慧小苏-智能体帮您完成。

---

### 1. 安装依赖

```bash
# 使用内网PYPI源
pip config set global.index-url http://packages.jsbchina.cn/repository/python-public/simple/
pip config set global.trusted-host packages.jsbchina.cn

pip install -r requirements.txt
```

`requirements.txt` 内容：
```
pandas>=1.3.0
pyyaml>=5.4
lightgbm>=3.3.0
joblib>=1.0.0
openpyxl>=3.0.0
```

### 2. 缓存机制（自动生效，无需配置）

首次加载 `metadata.yaml` 后，系统会自动在同目录生成 `.pkl` 缓存文件：

```
config/
metadata.yaml ← 源文件（8.67 MB）
metadata.pkl ← 自动生成的缓存（8.23 MB）
```

- **首次加载**：解析 YAML 并生成缓存（约 50s）
- **后续加载**：直接读取缓存（约 0.6s），**加速 90 倍**
- **自动失效**：YAML 文件修改时间比缓存新时，自动重新解析并重建缓存
- **手动刷新**：如需强制重建，直接删除 `config/metadata.pkl` 即可

### 3. 准备配置文件

项目使用 `config/config.yaml` 作为唯一配置入口，支持**变量替换**机制，实现"一处修改，多处生效"。

#### 3.1 配置文件结构

配置按**修改频率**分为五层，换模型时只需修改第1-2层：

| 层级 | 修改频率 | 配置项 | 说明 |
|------|---------|--------|------|
| 第1层 | 每次必改 | `project.work_no/model_id/product_code` | 工作编号、模型编号、产品代码 |
| 第2层 | 每次必改 | `model.path/sample.table_name/output.table_name` | 模型文件、样本表、输出表 |
| 第3层 | 业务调整时 | `platform/table_join_keys/extra_where_conditions` | 平台规则、关联键、过滤条件 |
| 第4层 | 环境升级时 | `sql_generation.*` | SQL生成参数（JOIN数、分区策略等） |
| 第5层 | 首次配置后固定 | `platform_mapping/var_type_mapping` | 英文映射、环境映射 |

#### 3.2 变量替换机制

配置中支持使用 `${变量名}` 占位符，会在加载时自动替换：

| 占位符 | 来源 | 示例值 |
|--------|------|--------|
| `${work_no}` | `project.work_no` | `01011939` |
| `${model_id}` | `project.model_id` | `MYJBV4_DZZY` |
| `${model_file_id}` | `project.model_file_id` | `MYJBV4_ZY` |
| `${product_code}` | `project.product_code` | `MYJBV4` |

**示例**：`sample.table_name` 配置为 `tmp_${work_no}_20260416_${product_code}_huisu_sample`，实际加载后变为 `tmp_01011939_20260416_MYJBV4_huisu_sample`。


#### 3.3 最小可运行配置（新模型接入时必改项）

```yaml
# ========== [高频] 第1层：核心标识（每次换模型必改） ==========
project:
  work_no: "01011939"         # 工作编号/项目编号
  model_id: "MYJBV4_DZZY"     # 模型编号（影响临时表命名）
  model_file_id: "MYJBV4_ZY"  # 模型文件标识
  product_code: "MYJBV4"      # 产品代码（用于变量替换、prd_sub_cls_cd条件）

# ========== [高频] 第2层：输入输出（每次换模型必改） ==========
model:
  path: input/${model_file_id}_lgb_model.model   # 模型文件路径

sample:
  table_name: tmp_${work_no}_20260416_${product_code}_huisu_sample
  key: apply_no
  fields:
    - apply_no
    - cust_id
    - cert_no
    - issue_time
    - apply_mth

output:
  table_name: tmp_${work_no}_20260421_${product_code}_var_output
  keep_columns:
    - apply_no

pipeline:
  mode: temp_table
  save_sql: output/${model_id}_pipeline_output.sql
  save_report: output/${model_id}_pipeline_report.md
  generate_score: true

# ========== [中频] 第3层：平台与业务规则（贷中模型需配置） ==========
platform: ""                  # 贷前留空；贷中填"字节"/"京东白条"等
platform_value: "myjb"        # $platform占位符替换值

# 行为变量平台优先级（当platform不匹配时按此顺序选择）
behavior_platform_priority:
  - "贷中行为变量-新底座"
  - "行为变量-总行"
  - "行为变量-消金"

# 各表关联键配置（覆盖metadata.yaml默认值）
table_join_keys:
  "wdyy_mrs.T_PBCI_SUMMARY_OTHER":
    join_key: "ci_rpt_id"
    partition_field: "part_id"
  "wdyy.T_CCRDYYF_Cust_Crdt_Info_Stats":
    join_key: "cust_id"
    partition_field: "part_id"

# 禁用变量黑名单配置（全局清单 + 模型专属补充）
blacklist_file: "data/禁用变量清单.txt"   # 全局禁用变量清单文件路径
blacklist_vars:
  # - "model_specific_var"  # 模型专属补充禁用变量

# 征信主键表配置（含征信变量时必须启用）
credit_primary_table:
  enabled: true
  table_name: "wdyy_mrs.t_pbci_summary_other"
  primary_key: "ci_rpt_id"
  sample_link_key: "be_qry_cert_num"
  sample_bridge_key: "cert_no"
  partition_field: "part_id"
  time_field: "rpt_tm"
  sample_time_field: "issue_time"
  time_window_days: 90
  md5_transform: true
  direction: "<="

# ========== [低频] 第4层：SQL生成参数（一般无需修改） ==========
sql_generation:
  max_subquery_join: 4        # 单临时表最大JOIN数
  coalesce_value: -999999     # 空值填充值
  partition_field: "dt"
  group_merge: true           # 同一平台多表合并为中间总表
  naming_style: "descriptive" # 临时表命名风格

  # 分区控制策略（优先级：by_table > by_platform > by_category > default）
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
        min_partition: "202601"

  # JOIN类型配置（征信变量内连接，行为变量左连接）
  join_types:
    by_category:
      "征信变量": "JOIN"
      "行为变量": "LEFT JOIN"
```

#### 3.4 配置项速查表

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `project.work_no` | ✅ | 工作编号，影响临时表前缀 |
| `project.model_id` | ✅ | 模型编号，影响临时表命名 |
| `project.product_code` | ✅ | 产品代码，用于`prd_sub_cls_cd`过滤 |
| `model.path` | ✅ | 模型文件路径（支持`${model_file_id}`变量） |
| `sample.table_name` | ✅ | 样本表名 |
| `sample.key` | ✅ | 样本表主键（如`apply_no`/`cust_id`） |
| `output.table_name` | ✅ | 最终输出表名 |
| `platform` | 贷中必填 | 模型所属平台，用于歧义变量自动选择 |
| `platform_value` | ✅ | `$platform`占位符替换值 |
| `credit_primary_table` | 含征信变量必填 | 征信桥接表配置，含`enabled/table_name/time_window_days/direction`等子项 |
| `table_join_keys` | 按需 | 覆盖元数据中的关联键/分区字段 |
| `variable_overrides` | 按需 | 强制指定异常变量的来源表 |
| `time_range_joins` | 按需 | 时间区间匹配（如`part_id`月份偏移） |
···

### 4. 准备变量元数据

当前已配置好。下面为配置方式介绍：

**方式一：直接编写 YAML**（参考 `config/example_metadata.yaml`）

```yaml
variables:
  - var_name: als_m12_id_nbank_max_monnum
    var_desc: 近12个月非银最大月申请次数
    source_table: edap.v_BRDT_APPLYLOANSTR_md5
    category: 外数
    platform: 百融
    partition_field: dt
    join_key: apply_no

tables:
  - table_name: edap.v_BRDT_APPLYLOANSTR_md5
    table_desc: 百融多头变量
    category: 外数
    platform: 百融
    partition_field: dt
    join_key: apply_no
    variables:
      - als_m12_id_nbank_max_monnum
```

**方式二：从 CSV 转换**

CSV 格式要求（制表符分隔，4列）：
| 字段名 | 字段含义 | 来源表 | 表描述 |
|--------|---------|--------|--------|
| als_m12_id_nbank_max_monnum | 近12个月非银最大月申请次数 | edap.v_BRDT_APPLYLOANSTR_md5 | 百融多头变量 |

```bash
python scripts/convert_csv_to_metadata.py \
    --input data/variable_dict.csv \
    --output config/metadata.yaml
```

或 Python API：
```python
from metadata import convert_csv_to_yaml

convert_csv_to_yaml(
    csv_path="data/variable_dict.csv",
    yaml_path="config/metadata.yaml"
)
```

**方式三：从 Excel（多列）转换**

```python
from utils.excel_to_yaml import convert_excel_to_yaml

convert_excel_to_yaml(
    excel_path="变量字典.xlsx",
    output_path="config/metadata.yaml",
    category_map={
        'edap.v_BRDT': '外数',
        'edap.v_credit': '征信'
    }
)
```

## 完整使用案例

### 案例一：一键执行完整任务流（推荐）

> **提示**：首次运行会自动生成 `metadata.pkl` 缓存（约50秒），后续加载直接读缓存（约0.6秒），**加速约90倍**。

#### 方式A：从配置文件自动读取参数（推荐）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# 将src加入Python路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from pipeline import LgbToSqlPipeline

def main():
    # 初始化Pipeline（自动加载config.yaml和metadata.yaml）
    pipeline = LgbToSqlPipeline(
        config_path='config/config.yaml',
        metadata_path='config/metadata.yaml'
    )
    
    # 执行完整任务流（所有参数从配置文件自动读取）
    result = pipeline.run(
        model_path=pipeline.config.model_path,
        sample_config={
            'table_name': pipeline.config.sample_table_name,
            'key': pipeline.config.sample_key,
            'fields': pipeline.config.sample_fields
        },
        output_config={
            'output_table': pipeline.config.output_table_name,
            'output_db': pipeline.config.output_database,
            'coalesce_value': pipeline.config.coalesce_value
        },
        mode=pipeline.config.pipeline_mode,
        save_sql=pipeline.config.pipeline_save_sql,
        generate_score=pipeline.config.pipeline_generate_score,
        score_config={
            'keep_columns': pipeline.config.output_keep_columns
        },
        save_report=pipeline.config.pipeline_save_report
    )
    
    print(f'入模变量数: {len(result["features"])}')
    print(f'JOIN SQL长度: {len(result["join_sql"])} 字符')
    print(f'打分SQL长度: {len(result["score_sql"]) if result["score_sql"] else 0} 字符')
    print(f'SQL已保存到: {pipeline.config.pipeline_save_sql}')

if __name__ == '__main__':
    main()
```

**运行方式**：
```bash
python run_full_pipeline.py
```

**优点**：
- 所有参数集中管理在 `config.yaml`，换模型时只需改配置文件
- 支持变量替换（`${work_no}`/`${model_id}`/`${product_code}`），避免多处硬编码
- 自动复用 `metadata.pkl` 缓存，后续执行秒级启动

#### 方式B：手动传入参数（快速测试/调试）

```python
from pipeline import LgbToSqlPipeline

pipeline = LgbToSqlPipeline(
    config_path="config/config.yaml",
    metadata_path="config/metadata.yaml"
)

result = pipeline.run(
    model_path="input/MYJBV4_ZY_lgb_model.model",
    sample_config={
        'table_name': 'tmp_01011939_20260416_MYJBV4_huisu_sample',
        'key': 'apply_no',
        'fields': ['apply_no', 'cust_id', 'cert_no', 'issue_time']
    },
    output_config={
        'output_table': 'tmp_01011939_20260421_MYJBV4_var_output',
        'coalesce_value': -999999
    },
    mode='temp_table',
    save_sql='output/MYJBV4_DZZY_pipeline_output.sql',
    generate_score=True,
    score_config={
        'keep_columns': ['apply_no']
    }
)
```

#### 控制台输出示例

```
================================================================================
配置信息
================================================================================
工作编号: 01011939
模型编号: MYJBV4_DZZY
SQL生成模式: temp_table
最大子查询关联数: 4
空值填充值: -999999

================================================================================
元数据概览
================================================================================
变量总数: 19223
表总数: 64
平台分布:
  行为变量-消金: 12个变量
  征信变量-消金: 16个变量
  征信变量-总行: 6个变量
  外部数据: 4个变量
  ...

================================================================================
模型解析结果
================================================================================
模型类型: LightGBM
入模变量数: 47
变量列表（前20个）:
  1. als_m12_id_nbank_max_monnum
  2. als_m3_id_nbank_orgnum
  ...

================================================================================
变量元数据报告
================================================================================
正常命中: 47 / 47 (100.0%)
未命中: 0
歧义变量: 0

================================================================================
JOIN执行计划
================================================================================
分组数: 5
  组1: 外部数据/百融 (apply_no) - 1张表, 2个变量
    - edap_mrs.BRDT_APPLYLOANSTR
  组2: 征信变量-消金 (report_no) - 16张表, 20个变量
    - wdyy_mrs.T_PBCI_SUMMARY_OTHER
    - wdyy_mrs.T_PBCI_LIMIT_USE_OTHER
    - ... (共16张表)
  组3: 征信变量-总行 (ci_rpt_id) - 6张表, 15个变量
    - ... (共6张表)
  组4: 行为变量-消金 (cust_id) - 12张表, 8个变量
    - ... (共12张表)
  组5: 模型分 (cert_no) - 1张表, 2个变量
    - sykj1.model_score_recall

================================================================================
打分SQL信息
================================================================================
临时表: 3个
SQL长度: 15234字符
================================================================================
Pipeline执行成功！
```

#### 生成的SQL示例

上述代码会生成两部分SQL，以下是简化示例：

**变量拼接SQL（临时表风格）**：

```sql
-- ===== 外部数据-百融 临时表 (apply_no) =====
DROP TABLE IF EXISTS tmp_01011939_20260423_MYJBV4_DZZY_wd_001;
CREATE TABLE tmp_01011939_20260423_MYJBV4_DZZY_wd_001 AS
SELECT a.apply_no AS apply_no,
       a.dt AS dt,
       a.als_m12_id_nbank_max_monnum,
       a.als_m3_id_nbank_orgnum
FROM (
    SELECT t.apply_no, t.dt, t.als_m12_id_nbank_max_monnum, t.als_m3_id_nbank_orgnum
        FROM edap_mrs.BRDT_APPLYLOANSTR t
    WHERE t.dt = '${biz_date}'
      AND t.apply_no IN (
          SELECT apply_no FROM tmp_01011939_20260416_MYJBV4_huisu_sample
      )
) a;

-- ... 其他分组临时表 ...

-- ===== 最终输出表 =====
DROP TABLE IF EXISTS model_score_input;
CREATE TABLE IF NOT EXISTS model_score_input AS
SELECT
    s.apply_no,
    s.cust_no,
    wd.als_m12_id_nbank_max_monnum,
    wd.als_m3_id_nbank_orgnum,
    -- ... 其他变量 ...
FROM tmp_01011939_20260416_MYJBV4_huisu_sample s
LEFT JOIN tmp_01011939_20260423_MYJBV4_DZZY_wd_001 wd ON s.apply_no = wd.apply_no
LEFT JOIN tmp_01011939_20260423_MYJBV4_DZZY_pbci_001 pbci ON s.ci_rpt_id = pbci.ci_rpt_id
-- ... 其他JOIN ...
WHERE s.dt = '${biz_date}';
```

**打分SQL（完整版）**：

```sql
DROP TABLE IF EXISTS tmp_01011939_20260423_MYJBV4_DZZY_var_fillna;
CREATE TABLE IF NOT EXISTS tmp_01011939_20260423_MYJBV4_DZZY_var_fillna AS
SELECT apply_no,
       NVL(als_m12_id_nbank_max_monnum, -999999) AS als_m12_id_nbank_max_monnum,
       -- ... 所有变量的NVL填充 ...
FROM model_score_input;

DROP TABLE IF EXISTS tmp_01011939_20260423_MYJBV4_DZZY_model_score;
CREATE TABLE IF NOT EXISTS tmp_01011939_20260423_MYJBV4_DZZY_model_score AS
SELECT apply_no,
       1 / (1 + exp(-((tree_0_score + tree_1_score + ... )+(-0.0)))) AS lgb2sql_score,
       CASE WHEN LEAST(...) = -999999 AND GREATEST(...) = -999999 THEN 1 ELSE 0 END AS all_null_flag
FROM (
    SELECT apply_no,
           CASE WHEN (als_m12_id_nbank_max_monnum is null and true==true or ...) THEN ...
           END AS tree_0_score,
           -- ... 每棵树的CASE WHEN ...
    FROM tmp_01011939_20260423_MYJBV4_DZZY_var_fillna
) t;

DROP TABLE IF EXISTS tmp_01011939_20260423_MYJBV4_DZZY_model_scorecard;
CREATE TABLE IF NOT EXISTS tmp_01011939_20260423_MYJBV4_DZZY_model_scorecard AS
SELECT *,
       round(CASE
           WHEN all_null_flag = 1 OR CAST(lgb2sql_score AS FLOAT) <= 0 OR CAST(lgb2sql_score AS FLOAT) >= 1 THEN -999999
           ELSE 533.903595 - 72.134752 * ln(CAST(lgb2sql_score AS FLOAT) / (1 - CAST(lgb2sql_score AS FLOAT)))
       END, 2) AS score_card
FROM tmp_01011939_20260423_MYJBV4_DZZY_model_score;
```

### 案例二：分步执行（灵活控制）

适用于需要自定义处理流程的场景，如批量处理多个模型、自定义变量过滤逻辑等。

> **提示**：`MetadataManager.load()` 会自动检测并使用 `metadata.pkl` 缓存。

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline_pkg.pipeline_core import LgbToSqlPipeline
from pipeline_pkg.feature_reporter import FeatureReporter
from pipeline_pkg.scorer import ScoreGenerator
from core.sql_builder import SQLBuilder
from core.models import OutputConfig
from metadata import MetadataManager
from core.config_loader import SQLConfig
from core.lgb_feature_extractor import LgbFeatureExtractor

# ========== 步骤1: 解析模型 ==========
extractor = LgbFeatureExtractor("input/MYJBV4_ZY_lgb_model.model")
extractor.load_from_file()
extractor.print_summary()  # 打印模型摘要

features = extractor.get_all_features()
valid_features = extractor.get_valid_features()

# ========== 步骤2: 加载配置和元数据 ==========
config = SQLConfig("config/config.yaml")
metadata = MetadataManager()
metadata.load("config/metadata.yaml")  # 自动使用.pkl缓存（如有）

# 应用变量覆盖（仅指定source_table，关联键从table_join_keys获取）
if config.variable_overrides:
    metadata.apply_variable_overrides(
        config.variable_overrides,
        table_join_keys=config.table_join_keys
    )

# ========== 步骤3: 生成变量报告 ==========
reporter = FeatureReporter(metadata, config)
report = reporter.generate_report(features)
reporter.print_report(report)

# 检查问题变量
missing_vars = report['missing_vars']
ambiguous_vars = report['ambiguous_vars']

if missing_vars:
    print(f"警告: {len(missing_vars)} 个变量未命中元数据")
if ambiguous_vars:
    print(f"注意: {len(ambiguous_vars)} 个变量匹配多张表，已按规则自动选择")

# ========== 步骤4: 生成JOIN SQL ==========
builder = SQLBuilder(metadata, config)

# 方式A: 临时表风格（适合调度执行，推荐）
sql_temp = builder.build_temp_table_sql(
    model_features=features,
    sample_config={
        'table_name': config.sample_table_name,
        'key': config.sample_key,
        'fields': config.sample_fields
    },
    output_config=OutputConfig(
        output_table=config.output_table_name,
        coalesce_value=config.coalesce_value
    )
)

# 方式B: CTE风格（更现代，可读性好，适合分析调试）
sql_cte = builder.build_cte_sql(
    model_features=features,
    sample_config={
        'table_name': config.sample_table_name,
        'key': config.sample_key,
        'fields': config.sample_fields
    },
    output_config=OutputConfig(
        output_table=config.output_table_name,
        coalesce_value=config.coalesce_value
    )
)

# 保存SQL
builder.save_sql(sql_temp, "output/join_sql_temp_table.sql")
builder.save_sql(sql_cte, "output/join_sql_cte.sql")

# 打印执行计划摘要
plan = builder.planner.plan(
    model_features=features,
    sample_table=config.sample_table_name,
    sample_key=config.sample_key
)
print(builder.generate_execution_summary(plan))

# ========== 步骤5: 生成打分SQL（可选） ==========
scorer = ScoreGenerator(config)
score_sql = scorer.generate(
    model_path="input/MYJBV4_ZY_lgb_model.model",
    keep_columns=['apply_no'],
    input_table=config.output_table_name,
    scorecard_shift=533.903595,
    scorecard_slope=72.134752,
    round_decimal=32
)

# 查看打分创建的临时表
tables = scorer.get_created_tables()
print(f"打分SQL将创建以下临时表: {tables}")
```

### 案例三：处理异常变量

场景：某些变量未命中元数据，或匹配到多张表导致歧义。

**解决步骤**：
1. 在 `config.yaml` 中配置 `variable_overrides`，强制指定来源表
2. 在 `config.yaml` 中配置 `table_join_keys`，指定该表的关联键和分区字段
3. 重新运行Pipeline，自动应用覆盖配置

```yaml
# config.yaml 中的配置示例
variable_overrides:
  # 场景A：变量无法自动匹配元数据（新上线变量）
  new_feature_v2:
    source_table: "edap_mrs.v_new_features"
  
  # 场景B：变量匹配多张表（同名变量存在于多个平台）
  cust_age:
    source_table: "wdyy_mrs.T_PBCI_SUMMARY_OTHER"

table_join_keys:
  "edap_mrs.v_new_features":
    join_key: "cert_no"
    partition_field: "dt"
```

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline_pkg.pipeline_core import LgbToSqlPipeline

pipeline = LgbToSqlPipeline(
    config_path="config/config.yaml",  # 包含 variable_overrides
    metadata_path="config/metadata.yaml"
)

# 运行时会自动应用覆盖配置
result = pipeline.run(
    model_path="input/MYJBV4_ZY_lgb_model.model",
    save_sql="output/result.sql"
)
```

### 案例四：仅生成变量提取SQL（不打分）

适用于只需要生成特征宽表、不需要模型打分的场景，如回溯验证、特征分析等。

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline_pkg.pipeline_core import LgbToSqlPipeline

pipeline = LgbToSqlPipeline(
    config_path="config/config.yaml",
    metadata_path="config/metadata.yaml"
)

result = pipeline.run(
    model_path="input/MYJBV4_ZY_lgb_model.model",
    save_sql="output/join_only.sql",
    generate_score=False  # 不生成打分SQL
)

# 只获取变量拼接SQL
join_sql = result['join_sql']
print(f"生成变量提取SQL，长度: {len(join_sql)} 字符")
```

### 案例五：使用不同模型格式

项目支持三种模型文件格式，自动根据后缀识别：

| 后缀 | 格式 | 适用场景 |
|------|------|---------|
| `.pkl` | Python pickle（LightGBM Booster） | Python训练环境导出的模型 |
| `.pmml` | PMML标准格式 | 跨平台部署、Java环境 |
| `.model` | LightGBM文本格式 | LightGBM原生save_model输出 |

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from model_loaders import load_model

# load_model 自动根据后缀选择加载器
loader = load_model("input/model.pkl")    # PklModelLoader
# loader = load_model("input/model.pmml")   # PmmlModelLoader
# loader = load_model("input/model.model")  # TextModelLoader

features = loader.get_features()
print(f"提取到 {len(features)} 个变量")
print(f"前10个变量: {features[:10]}")
```

### 案例六：元数据统计报告

在模型开发或元数据维护阶段，经常需要了解当前元数据的整体画像，比如变量覆盖了多少张表、各平台的变量分布、元数据字段的完整率等。

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline_pkg.pipeline_core import LgbToSqlPipeline

pipeline = LgbToSqlPipeline(
    config_path="config/config.yaml",
    metadata_path="config/metadata.yaml"
)

# 方式一：直接打印统计报告到控制台
pipeline.print_metadata_statistics()

# 方式二：获取统计字典，用于进一步分析或导出
stats = pipeline.get_metadata_statistics()

# 查看总体概览
print(f"变量总数: {stats['overview']['total_variables']}")
print(f"表总数: {stats['overview']['total_tables']}")

# 查看分类分布
for cat, count in stats['category_distribution'].items():
    print(f"  {cat}: {count} 个变量")

# 查看元数据完整性
comp = stats['completeness']
print(f"来源表完整率: {comp['has_source_table'] / comp['total'] * 100:.1f}%")
print(f"描述完整率: {comp['has_description'] / comp['total'] * 100:.1f}%")

# 查看特殊变量
special = stats['special_variables']
print(f"跨表重复变量: {special['duplicate_count']} 个")
print(f"疑似主键: {special['likely_key_count']} 个")

# 导出为JSON
json_str = pipeline.metadata.get_statistics_json()
with open("output/metadata_stats.json", "w", encoding="utf-8") as f:
    f.write(json_str)

```

### 案例七：回归测试

在修改配置或代码后，需要验证所有模型仍能正常生成SQL。项目提供了回归测试脚本 `tests/test_regression.py`，自动遍历 `input/` 目录下的所有模型文件及其对应配置，完整执行流水线并验证输出。

**运行方式：**

```bash
# 运行全部回归测试
python tests/test_regression.py

# 详细输出模式
python tests/test_regression.py --verbose

# 作为 unittest 运行
python -m unittest tests.test_regression -v
```

**测试覆盖：**

| 验证项 | 说明 |
|--------|------|
| 流水线执行 | 不抛异常，正常完成 |
| SQL 文件生成 | 文件存在且非空 |
| 报告文件生成 | 文件存在且非空 |
| 入模变量数 | > 0 |
| JOIN SQL 长度 | > 0 |
| SQL 内容检查 | 包含 `DROP TABLE IF EXISTS` 和 `CREATE TABLE` |

**当前支持的模型：**

| 模型文件 | 配置文件 | 变量数 |
|---------|---------|--------|
| `jdjt_gkb_20260316_lgb_best_plus.model` | `JDJT_GKB.yaml` | ~149 |
| `MTSHF_DQ_FUZHAI_lgb_model.model` | `MTSHF_DQ_FUZHAI.yaml` | ~198 |
| `MYJBV4_ZY_lgb_model.model` | `MYJBV4_ZY.yaml` | ~35 |
| `zjfxj_zyb_lgb_v1.model` | `ZJFXJ_ZYB.yaml` | ~50 |

**添加新模型到回归测试：**

编辑 `tests/test_regression.py` 中的 `MODEL_CONFIG_MAP` 字典：

```python
MODEL_CONFIG_MAP = {
    "jdjt_gkb_20260316_lgb_best_plus.model": "JDJT_GKB.yaml",
    "MTSHF_DQ_FUZHAI_lgb_model.model": "MTSHF_DQ_FUZHAI.yaml",
    "MYJBV4_ZY_lgb_model.model": "MYJBV4_ZY.yaml",
    "zjfxj_zyb_lgb_v1.model": "ZJFXJ_ZYB.yaml",
    # 添加新模型
    "your_model.model": "your_model.yaml",
}
```

### 案例八：SQL验证工具（数据质量校验）

在模型上线或回溯后，需要验证生成的变量宽表数据质量。项目提供了 `scripts/analysis/generate_validation_sql.py` 脚本，自动生成9维度验证SQL。

#### 使用方式

```bash
# 基础用法（从配置自动推断模型路径）
python scripts/analysis/generate_validation_sql.py \
    -m MYJBV4_ZY \
    -o tmp_01011939_20260429_MYJBV4_ZY_var_output \
    -s tmp_01011939_20260429_MYJBV4_ZY_sample

# 指定模型文件路径
python scripts/analysis/generate_validation_sql.py \
    -m MYJBV4_ZY \
    --model-path input/MYJBV4_ZY_lgb_model.model \
    -o tmp_01011939_20260429_MYJBV4_ZY_var_output \
    -s tmp_01011939_20260429_MYJBV4_ZY_sample

# 指定输出目录
python scripts/analysis/generate_validation_sql.py \
    -m MYJBV4_ZY \
    -o tmp_01011939_20260429_MYJBV4_ZY_var_output \
    -s tmp_01011939_20260429_MYJBV4_ZY_sample \
    --output-dir output/validation_sql
```

#### 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `-m` / `--model-id` | ✅ | 模型标识（对应 `config/models/{model_id}.yaml`） |
| `-o` / `--output-table` | ✅ | 变量输出表名 |
| `-s` / `--sample-table` | ✅ | 样本表名 |
| `--model-path` | 否 | 模型文件路径（默认从配置自动推断） |
| `--output-dir` | 否 | 输出目录（默认 `output/validation_sql`） |

#### 生成的验证维度

| # | 验证维度 | 输出指标 | 阈值建议 |
|---|---------|---------|---------|
| 1 | 样本量一致性 | `sample_cnt`, `output_cnt`, `diff_pct` | `diff_pct` ∈ [-0.1%, +0.1%] |
| 2 | 变量缺失率 | 各变量`missing_pct` | 核心变量 < 10%，一般变量 < 50% |
| 3 | 高缺失率变量 | `variable_name`, `missing_pct` | 缺失率 ≥ 50% 需关注 |
| 4 | 数据波动 | `avg`, `std`, `min`, `max`, `median` | 跨月均值变化 < ±20% |
| 5 | 环比波动 | `mom_pct`（月度环比变化率） | 变化率 > ±30% 需关注 |
| 6 | 主键唯一性 | 重复记录数、总记录数、唯一主键数 | 重复数应为0 |
| 7 | 评分分布 | `score_avg`, `score_p50`, `all_null_pct` | `all_null_pct` < 5% |
| 8 | 评分区间 | 7档评分区间占比 | 跨月区间变化 < ±5% |
| 9 | 变量覆盖度 | 各变量有效值覆盖率 | 核心变量 > 90% |

#### 输出文件

脚本执行后生成两个文件：

- **`output/validation_sql/{model_id}_validation.sql`** — 可直接在Hive/Spark执行的验证SQL
- **`output/validation_sql/{model_id}_validation_report.md`** — Markdown格式分析报告（含SQL片段和指标说明）

#### 使用流程

```
步骤1: 执行模型Pipeline生成变量宽表
        ↓
步骤2: 运行验证脚本生成验证SQL
        ↓
步骤3: 在Hive/Spark中执行验证SQL
        ↓
步骤4: 查看Markdown报告分析结果
        ↓
步骤5: 如发现异常（如缺失率突增），排查数据源或配置
```
