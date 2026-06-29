# lgb2sql 配置详解

> 本文档包含所有配置项的详细说明、配置示例和策略组合示例。

---

## 配置详解

### 配置项总览

`config.yaml` 是 lgb2sql 的核心配置文件，所有控制策略、命名规则和异常处理都集中在此。下表列出所有一级配置项及其作用：

| 配置项 | 作用 | 是否必填 |
|--------|------|----------|
| `project` | 项目基本信息（工作编号、模型ID、日期格式） | 是 |
| `platform` | 歧义变量平台解析与 `$platform` 占位符替换 | 否 |
| `sample` | 样本表配置（表名、关联键、保留字段） | 是 |
| `output` | 输出表配置（表名、数据库、分区语句） | 否 |
| `sql_generation` | SQL生成核心参数（JOIN数限制、分区策略、命名风格等） | 是 |
| `post_process` | 后处理配置（去重、空值填充、全空标记） | 否 |
| `scorecard` | 评分卡参数（基础分、PDO、分数上下限） | 否 |
| `var_type_mapping` | 变量分类 → 英文缩写映射（用于临时表命名） | 是 |
| `platform_mapping` | 平台名称 → 英文缩写映射（用于临时表命名） | 是 |
| `variable_overrides` | 变量级覆盖（处理未命中/歧义变量） | 否 |
| `table_join_keys` | 表级关联键和分区字段覆盖 | 否 |
| `variable_aliases` | 变量名别名映射（模型名→数据库列名） | 否 |
| `blacklist_file` | 禁用变量清单文件路径 | 否 |
| `blacklist_vars` | 禁用变量黑名单（YAML内联配置） | 否 |
| `credit_primary_table` | 征信桥接表配置（ci_rpt_id 关联） | 否 |
| `custom_join_conditions` | 自定义JOIN条件（MD5、时间偏移等） | 否 |
| `time_range_joins` | 时间区间匹配配置（近因匹配） | 否 |
| `extra_where_conditions` | 额外WHERE条件（分类/平台/表三级） | 否 |

---

### 自动缓存机制（无需配置）

`lgb2sql` 内置自动 Pickle 缓存机制，用于加速大型 YAML 元数据文件的加载。

#### 工作原理

```
首次加载:
  metadata.yaml ──► yaml.safe_load() ──► 解析数据 ──► 自动生成 metadata.pkl
                                                          ↓
后续加载:                                                 使用缓存
  metadata.yaml ──► 检测 mtime ──► 缓存更新? ──► 否 ──► pickle.load()
                              │                      ↑
                              └─ 是 ──► 重新解析 ────┘
```

#### 缓存文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `config/metadata.yaml` | ~8.7 MB | 源 YAML 元数据文件 |
| `config/metadata.pkl` | ~8.2 MB | 自动生成的二进制缓存 |

#### 性能对比

| 加载方式 | 耗时 | 加速比 |
|----------|------|--------|
| `yaml.safe_load` (无缓存) | ~51s | 1.0× |
| `pickle.load` (有缓存) | ~0.6s | **~90×** |

#### 管理缓存

- **自动生成**：首次加载 YAML 后自动在同目录生成 `.pkl` 文件
- **自动失效**：YAML 文件修改后自动检测并重建缓存
- **手动刷新**：直接删除 `.pkl` 文件，下次加载自动重建
- **无需配置**：完全透明，不增加任何配置项

---

---


### project（项目基本信息）

```yaml
project:
  work_no: "01011939"         # 工作编号
  model_id: "MYJBV4_DZZY"     # 模型编号
  date_format: "yyyyMMdd"     # 日期格式
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `work_no` | `"FX2025"` | 工作编号，用于临时表前缀命名 | 按实际项目编号填写，如 `"01011939"` |
| `model_id` | `"M001"` | 模型编号，用于临时表命名区分不同模型 | 使用有意义的模型代号，如 `"MYJBV4_DZZY"` |
| `date_format` | `"yyyyMMdd"` | 日期格式，用于临时表日期后缀 | 一般无需修改 |

**影响范围**：所有临时表名格式为 `tmp_{work_no}_{date}_{model_id}_{type}_{seq}`，如 `tmp_01011939_20260421_MYJBV4_DZZY_wd_001`。

---

### platform（平台解析配置）

```yaml
platform: ""                  # 指定平台，如"字节"、"京东白条"等
platform_value: "myjb"        # $platform 占位符替换值
behavior_platform_priority:   # 行为变量平台优先级（歧义时按顺序选择）
  - "贷中行为变量-新底座"
  - "行为变量-总行"
  - "行为变量-消金"
  - "字节"
  - "京东白条"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `platform` | `""` | 指定当前模型所属平台，用于歧义变量表选择 | 贷前模型填 `""`，贷中模型填 `"字节"` 或 `"京东白条"` |
| `platform_value` | `"myjb"` | 替换表名中 `$platform` 占位符的值 | 借呗填 `"myjb"`，月付填 `"dyf"`，白条填 `"rbt"` |
| `behavior_platform_priority` | 见上方 | 行为变量存在多平台候选时的优先级顺序 | 根据实际数据底座覆盖范围调整顺序 |

**工作原理**：
1. 当变量匹配到多张表（歧义）时，若某张表的平台等于 `platform` 配置，则优先选择该表
2. 若 `platform` 为空或不匹配，按 `behavior_platform_priority` 顺序选择第一个有变量命中的平台
3. 表名中的 `$platform` 会被替换为 `platform_value`，如 `ads.ads_risk_$platform_cust_dz_indicator_ss` → `ads.ads_risk_myjb_cust_dz_indicator_ss`

---

### sample（样本表配置）

```yaml
sample:
  table_name: tmp_01011939_20260421_myjbv4_huisu_sample
  key: apply_no
  fields:
    - apply_no
    - cust_id
    - cert_no
    - issue_time
    - apply_mth
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `table_name` | 无 | 样本表全名 | 替换为实际样本表，支持多级分区表 |
| `key` | `"apply_no"` | 样本表主键/关联键 | 一般为 `apply_no`（授信）或 `cert_no`（贷中） |
| `fields` | `[]` | 样本表需要保留到最终输出的字段 | 至少包含关联键和时间字段（如 `issue_time`） |

**重要提醒**：
- 若使用征信变量，样本表必须包含 `cert_no`（用于桥接表关联）
- 若使用时间区间匹配，样本表必须包含配置中的 `sample_time_field`（如 `issue_time`）
- `fields` 中的字段会出现在最终输出表中

---

### output（输出表配置）

```yaml
output:
  table_name: edap.model_feature_output
  database: ""
  partition_clause: ""

  # 保留列（主键等，会输出到最终打分表）
  keep_columns:
    - apply_no

  # 样本表额外字段输出控制
  # true: 在 model_score 和 model_scorecard 表中自动包含 sample.fields 中的所有字段
  # false: 只输出 keep_columns 中的字段
  include_sample_fields: true

  # 变量字段输出控制（在 model_score 和 model_scorecard 表中）
  variable_output:
    enabled: false          # 默认不输出变量字段
    sort_by_importance: true  # 按特征重要度降序排列
    top_n: 0                # 输出前N个变量，0表示全部
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `table_name` | `"model_score_input"` | 最终输出表名 | 按项目规范填写，如 `edap.myjbv4_model_input` |
| `database` | `""` | 输出数据库（Hive中可选） | 如需指定数据库则填写，否则留空 |
| `partition_clause` | `""` | 建表分区语句 | 如 `PARTITIONED BY (dt STRING)` |
| `keep_columns` | `["apply_no"]` | 保留列（主键等） | 最终会输出到 model_score 和 model_scorecard 表 |
| `include_sample_fields` | `true` | 是否自动包含 sample.fields 中的字段 | 建议保持 `true`，确保样本表字段完整输出 |
| `variable_output.enabled` | `false` | 是否输出模型变量字段 | 需要调试或分析变量时设为 `true` |
| `variable_output.sort_by_importance` | `true` | 变量是否按重要度排序 | 保持 `true` 即可 |
| `variable_output.top_n` | `0` | 输出前N个变量（0表示全部） | 限制输出变量数量时填写正整数 |

---

### sql_generation（SQL生成核心参数）

这是最重要的配置节，包含分区控制、JOIN策略、命名风格等核心控制逻辑。

```yaml
sql_generation:
  max_subquery_join: 4
  coalesce_value: -999999
  partition_field: "dt"
  partition_var: "${biz_date}"
  group_merge: true
  naming_style: "descriptive"
```

#### 基础参数

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `max_subquery_join` | `3` | 单临时表内最大子查询JOIN数 | 表多且变量分散时调大（如4-6），表少时调小（如2-3） |
| `coalesce_value` | `-999999` | 空值填充值 | 与模型训练时的缺失值填充保持一致 |
| `partition_field` | `"dt"` | 默认分区字段 | 按实际数据底座分区字段填写，如 `part_id`、`data_dt` |
| `partition_var` | `"${biz_date}"` | 分区变量占位符 | 当前配置下未被直接使用（见下方说明），保留作为新增表未配置时的默认回退机制 |
| `group_merge` | `true` | 是否启用组内合并 | 建议保持 `true`，可减少最终JOIN层数 |
| `naming_style` | `"descriptive"` | 临时表命名风格 | `"descriptive"` 便于调试，`"simple"` 更简洁 |

#### credit_platforms（征信平台识别配置）

用于配置哪些平台属于征信类变量，影响 SQL 生成中的关联键选择和分区控制逻辑。

```yaml
sql_generation:
  credit_platforms:
    - "征信变量-消金"
    - "征信变量-总行"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `credit_platforms` | `["征信变量-消金", "征信变量-总行"]` | 征信平台名称列表 | 新增征信类平台时需同步添加，如 `"xxx"` |

**作用机制**：
1. **关联键选择**：征信类平台默认使用 `ci_rpt_id`（征信报告ID）作为关联键，非征信类使用 `cert_no`（身份证号）
2. **分区控制**：征信类平台自动应用 `partition_control` 中征信变量的分区策略
3. **JOIN类型**：征信类平台默认使用 `JOIN`（内连接），确保必须命中征信报告

> **注意**：此配置替代了早期版本中基于平台名称子串匹配（如包含"征信"）的识别方式，改为显式配置，避免误判。

> **关于 `partition_var: "${biz_date}"` 的当前状态说明**
>
> 在当前业务配置下，`${biz_date}` **未被任何表直接使用**。原因如下：
> 1. `partition_control` 已为所有表类型（征信变量、行为变量、贷中行为变量、外部数据）显式配置了 `range` 策略，生成的条件是 `partition_field >= min_partition`（如 `part_id >= 202512`），而非 `dt = '${biz_date}'`。
> 2. `time_range_joins` 中的表使用等号匹配或范围匹配，同样不依赖 `${biz_date}`。
> 3. 该变量保留作为**默认回退机制**：当后续新增表未在 `partition_control` 中配置时，代码可能回退到等值匹配 `dt = '${biz_date}'`。
>
> 如需让某张表按业务日期精确匹配分区，可将其配置为 `strategy: "equality"`（不填 `min_partition`），此时将生成 `dt = '${biz_date}'`。

#### join_types（JOIN类型配置）

```yaml
join_types:
  by_category:
    "征信变量": "JOIN"
    "行为变量": "LEFT JOIN"
  by_platform:
    "征信变量-消金": "JOIN"
    "征信变量-总行": "JOIN"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `by_category` | `{}` | 按分类配置JOIN类型 | 征信变量建议用 `JOIN`（必须命中），外数/行为可用 `LEFT JOIN` |
| `by_platform` | `{}` | 按平台配置JOIN类型 | 优先级高于 `by_category`，可精细控制 |

**注意**：`JOIN` 表示内连接（只保留匹配上的样本），`LEFT JOIN` 表示左连接（保留所有样本，未匹配填NULL）。征信变量通常用 `JOIN` 因为必须命中征信报告。

---

### post_process（后处理配置）

```yaml
post_process:
  deduplicate: true
  dedup_keys: ["apply_no"]
  dedup_order_field: "dt"
  dedup_order_desc: true
  fill_null: true
  fill_value: -999999
  null_flag: true
  null_flag_name: "all_null_flag"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `deduplicate` | `true` | 是否对样本表去重 | 样本表有重复时设为 `true` |
| `dedup_keys` | `["apply_no"]` | 去重键 | 按实际主键填写 |
| `dedup_order_field` | `"dt"` | 去重排序字段 | 取最新记录时填时间字段 |
| `dedup_order_desc` | `true` | 是否降序 | `true` 取最新，`false` 取最早 |
| `fill_null` | `true` | 是否填充空值 | 必须与模型训练一致 |
| `fill_value` | `-999999` | 空值填充值 | 与 `coalesce_value` 保持一致 |
| `null_flag` | `true` | 是否标记全空样本 | 建议启用，便于后续排查 |
| `null_flag_name` | `"all_null_flag"` | 全空标记字段名 | 一般无需修改 |

---

### scorecard（评分卡配置）

```yaml
scorecard:
  base_score: 700
  pdo: 0.1
  odds_at_base: 50
  score_min: 300
  score_max: 900
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `base_score` | `700` | 基础分 | 按业务评分卡标准填写 |
| `pdo` | `0.1` | PDO（翻倍odds分差） | 与模型开发时的评分卡参数一致 |
| `odds_at_base` | `50` | 基础分对应odds | 一般无需修改 |
| `score_min` | `300` | 最低分 | 按业务要求填写 |
| `score_max` | `900` | 最高分 | 按业务要求填写 |

**公式**：`score = base_score - pdo * ln(odds) / ln(2)`，其中 `odds = score / (1 - score)`

---

### var_type_mapping & platform_mapping（命名映射）

这两组映射用于生成临时表的英文缩写名称。

```yaml
var_type_mapping:
  行为变量: "bh"
  征信变量: "pbci"
  外部数据: "ed"
  模型分: "modelscore"

platform_mapping:
  百融: "br"
  字节: "zj"
  征信变量-消金: "xj_pbci"
  行为变量-消金: "xj_bh"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `var_type_mapping` | 见代码 | 分类 → 英文缩写 | 新增分类时需同步添加映射 |
| `platform_mapping` | 见代码 | 平台 → 英文缩写 | 新增平台时需同步添加映射 |

**命名规则**：临时表名 = `tmp_{work_no}_{date}_{model_id}_{type}_{seq}`，其中 `{type}` 由 `platform_mapping` + `var_type_mapping` 组合而成，如 `xj_pbci`、`zj_bh`。

---

### variable_overrides（变量覆盖配置）

用于处理异常变量：未命中元数据、或命中多张表（歧义）。

```yaml
variable_overrides:
  unclear_terms:
    source_table: "wdyy.t_zxysblhs_zxys_dz_realtime_rollback"
  loan_amt_m1:
    source_table: "T_CC_Cust_Repay_Info_Stats"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `{var_name}.source_table` | 无 | 强制指定变量的来源表 | 仅需填写表名，关联键和分区字段自动从 `table_join_keys` 获取 |

**优先级**：`variable_overrides` > 元数据自动匹配

**使用场景**：
- 变量未命中任何元数据表
- 变量命中多张表（歧义）
- 需要强制将变量映射到特定表（即使元数据中有其他匹配）

---

### table_join_keys（表级关联键覆盖）

用于批量覆盖某张表的关联键和分区字段，优先级高于元数据默认值。

```yaml
table_join_keys:
  "ads.ads_risk_$platform_cust_dz_indicator_ss":
    join_key: "cust_id"
    partition_field: "data_dt"
  "jsbrpt_mrs.zxbl_his_icr_result_his":
    join_key: "ci_rpt_id"
  # 分区字段为空表示不自动添加分区条件（由 time_range_joins 控制）
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `{table_name}.join_key` | 元数据默认值 | 覆盖该表的关联键 | 当元数据中的关联键有误时使用 |
| `{table_name}.partition_field` | 元数据默认值 | 覆盖该表的分区字段 | 设为 `""` 可禁用自动分区条件 |

**优先级**：`table_join_keys` > `metadata.yaml` 默认值

**使用场景**：
- 元数据中的关联键有误，需要统一修正
- 不同项目使用同一份元数据，但关联键需求不同
- 需要禁用某张表的自动分区条件（配合 `time_range_joins` 使用）

---

### blacklist_vars（禁用变量黑名单）

支持两种配置方式（合并生效）：

1. **`blacklist_file`**：指定外部清单文件路径（每行一个变量名）
2. **`blacklist_vars`**：直接在 YAML 中列变量名

两者合并使用：YAML 中直接定义的变量 + 外部文件加载的变量 = 完整黑名单，自动去重。

```yaml
# 方式1：外部清单文件（推荐用于全局通用禁用变量）
blacklist_file: "data/禁用变量清单.txt"

# 方式2：YAML内联配置（推荐用于模型专属补充变量）
blacklist_vars:
  - "sensitive_var_name"
  - "cust_id_card"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `blacklist_file` | `""` | 禁用变量清单文件路径 | 全局通用清单单独维护，便于多模型复用 |
| `blacklist_vars` | `[]` | YAML内联禁用变量列表 | 添加当前模型专属的禁用变量 |

**效果**：入模变量命中黑名单时，报告阶段输出告警信息，最终警告汇总统计命中数量。

**使用建议**：
- 全局通用禁用变量（如合规禁用、敏感变量）放在 `data/禁用变量清单.txt`，所有模型共用
- 模型专属禁用变量（如已知问题的特征）放在 `blacklist_vars` 中
- 关闭文件加载：将 `blacklist_file` 置空或删除该配置项

---

### credit_primary_table（征信桥接表配置）

用于征信变量的两级JOIN：样本表（`cert_no`）→ 征信主键表（`ci_rpt_id`）→ 征信变量表（`ci_rpt_id`）。

```yaml
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
  time_expr: "to_date(substr({field}, 1, 10))"
  sample_expr: "to_date({field})"
  direction: "<="
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `enabled` | `true` | 是否启用桥接表 | 使用征信变量时设为 `true` |
| `table_name` | `"wdyy_mrs.t_pbci_summary_other"` | 征信主键表 | 包含 `ci_rpt_id` 和 `cert_no` 映射关系的表 |
| `primary_key` | `"ci_rpt_id"` | 征信主键 | 一般为 `ci_rpt_id` |
| `sample_link_key` | `"be_qry_cert_num"` | 主键表中与样本关联的字段 | 意义同 `cert_no` |
| `sample_bridge_key` | `"cert_no"` | 样本表关联字段 | 样本表中的证件号字段 |
| `partition_field` | `"part_id"` | 主键表分区字段 | 按实际分区字段填写 |
| `time_field` | `"rpt_tm"` | 征信报告时间字段 | 精确到秒的时间字段 |
| `sample_time_field` | `"issue_time"` | 样本时间字段 | 用于时间窗口过滤 |
| `time_window_days` | `90` | 匹配窗口天数 | 取样本时间前90天内的征信报告 |
| `md5_transform` | `true` | 是否MD5转换 | 样本 `cert_no` = MD5(主键表 `be_qry_cert_num`) 时设为 `true` |
| `time_expr` | `"to_date(substr({field}, 1, 10))"` | 征信时间转换 | `{field}` 会被替换为实际字段名 |
| `sample_expr` | `"to_date({field})"` | 样本时间转换 | `{field}` 会被替换为实际字段名 |
| `direction` | `"<="` | 时间方向 | `"<="` 表示征信时间 ≤ 样本时间 |

**生成的SQL结构**：

```sql
-- 桥接表：关联样本表与征信主键表
SELECT s.apply_no, p.ci_rpt_id
FROM sample_table s
JOIN wdyy_mrs.t_pbci_summary_other p
  ON s.cert_no = MD5(p.be_qry_cert_num)
  AND to_date(substr(p.rpt_tm, 1, 10)) <= to_date(s.issue_time)
  AND DATEDIFF(to_date(s.issue_time), to_date(substr(p.rpt_tm, 1, 10))) <= 90
WHERE p.part_id >= min_partition;
```

---

### custom_join_conditions（自定义JOIN条件）

用于配置复杂的表关联条件，支持 MD5 转换、时间偏移、多字段关联等。

```yaml
custom_join_conditions:
  by_table:
    "ads.ads_risk_$platform_cust_dz_indicator_ss":
      join_key: "cert_no"
      sample_key: "cert_no"
      md5_transform: true
      time_offset:
        field: "issue_time"
        offset_days: -2
        target_field: "data_dt"
        target_expr: "cast(to_char(to_date({field}, 'yyyyMMdd') - 2, 'yyyyMMdd') AS int)"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `by_table.{table}` | 无 | 按表配置自定义JOIN | 优先级最高 |
| `join_key` | 元数据默认值 | 目标表关联键 | 覆盖默认关联键 |
| `sample_key` | 与 `join_key` 相同 | 样本表关联字段 | 当样本表字段名与目标表不同时配置 |
| `md5_transform` | `false` | 是否MD5转换 | 样本字段 = MD5(表字段) 时设为 `true` |
| `time_offset` | 无 | 时间偏移配置 | 用于申请时间减N天匹配数据日期 |
| `custom_on_clause` | 无 | 自定义ON条件 | 完全覆盖默认ON条件（高级用法） |

**time_offset 子配置**：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `field` | 样本表时间字段 | `"issue_time"` |
| `offset_days` | 偏移天数（负数为提前） | `-2` |
| `target_field` | 目标表时间字段 | `"data_dt"` |
| `target_expr` | 目标表时间字段表达式 | `"cast(to_char(to_date({field}, 'yyyyMMdd') - 2, 'yyyyMMdd') AS int)"` |

**生成的SQL结构**：

```sql
SELECT t.cert_no, t.var1, t.var2
FROM ads.ads_risk_myjb_cust_dz_indicator_ss t
WHERE t.cert_no IN (
    SELECT MD5(cert_no) FROM sample WHERE dt = '${biz_date}'
)
AND t.data_dt = cast(to_char(to_date(issue_time, 'yyyyMMdd') - 2, 'yyyyMMdd') AS int);
```

---

### time_range_joins（时间区间匹配配置）

用于需要通过时间区间关联的表（非等值匹配）。

```yaml
time_range_joins:
  "wdyy_mrs.T_CC_Cust_Crdt_Info_Stats":
    match_mode: "equality"
    time_field: "part_id"
    sample_time_field: "issue_time"
    time_expr: "to_char(TO_DATE({field}::text, 'YYYYMM') + INTERVAL '1 month', 'YYYYMM')"
    sample_expr: "to_char(TO_DATE({field}::text, 'YYYYMMdd'), 'YYYYMM')"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `match_mode` | `"range"` | 匹配模式：`equality`（等号）或 `range`（范围） | 跨月份精确匹配用 `equality`，近因匹配用 `range` |
| `time_field` | 无 | 变量表时间字段 | 按实际字段填写 |
| `sample_time_field` | `"issue_time"` | 样本表时间字段 | 按实际字段填写 |
| `time_expr` | `"to_date({field})"` | 变量表时间转换 | `{field}` 会被替换 |
| `sample_expr` | `"to_date({field})"` | 样本表时间转换 | `{field}` 会被替换 |

**range 模式额外配置**：

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `time_function` | `"DATEDIFF"` | 时间函数：`DATEDIFF` 或 `MONTHS_BETWEEN` | 按天计算用 `DATEDIFF`，按月用 `MONTHS_BETWEEN` |
| `window` | `90` | 时间窗口长度 | `DATEDIFF` 为天，`MONTHS_BETWEEN` 为月 |
| `direction` | `"<="` | 时间方向约束 | `"<="` 表时间在样本时间之前，`">="` 之后，`"between"` 为双向区间 |
| `dedup` | `false` | 是否在子查询内去重 | 变量表存在多对一时设为 `true` |
| `dedup_partition_by` | `"${sample_key}"` | 去重分区键 | 默认按样本关联键分区 |
| `dedup_order_by` | `"${time_field} DESC"` | 去重排序规则 | 默认按时间字段降序取最新 |
| `output_time_field` | `""` | 输出去重后的时间字段别名 | 需在 SELECT 中使用该字段时配置 |

**两种模式的区别**：

| 特性 | `equality` 模式 | `range` 模式 |
|------|-----------------|--------------|
| 分区条件 | 不限制 `partition_field = '${biz_date}'` | 限制 `partition_field = '${biz_date}'` |
| 去重方式 | 无需去重 | `ROW_NUMBER()` 去重（或配置 `dedup: true`） |
| 适用场景 | 跨月份精确匹配（如 part_id+1月 = issue_time月份） | 近因匹配（如90天内最新征信报告） |
| SQL复杂度 | 简单 | 复杂（带子查询和窗口函数） |

**direction 为 `between` 时的特殊行为**：

当 `direction: "between"` 时，SQL 生成逻辑会：
1. 使用 `MONTHS_BETWEEN` 计算两个时间的月数差
2. 生成 `BETWEEN 0 AND {window}` 条件（如 `BETWEEN 0 AND 3`）
3. 同时输出格式化后的时间字段（如 `formatted_score_date`），供后续关联使用

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

---

### extra_where_conditions（额外WHERE条件）

用于为特定分类/平台/表添加额外的WHERE限制条件。

```yaml
extra_where_conditions:
  by_category:
    "行为变量":
      - "prd_sub_cls_cd IS NOT NULL"
  by_platform:
    "行为变量-总行":
      - "part_id >= 202412"
  by_table:
    "wdyy_mrs.T_CC_Cust_Crdt_Info_Stats":
      - "prd_sub_cls_cd IN ('MYJBV4')"
      - "part_id >= 202602"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `by_category` | `{}` | 按分类添加条件 | 最低优先级 |
| `by_platform` | `{}` | 按平台添加条件 | 中等优先级，覆盖分类配置 |
| `by_table` | `{}` | 按表添加条件 | 最高优先级，覆盖平台和分类配置 |

**优先级**：`by_table` > `by_platform` > `by_category`

**使用场景**：
- 限定产品类型（如 `prd_sub_cls_cd IN ('MYJBV4')`）
- 限定时间范围（如 `part_id >= 202602`）
- 排除异常数据（如 `prd_sub_cls_cd IS NOT NULL`）

**注意**：征信变量的分区条件（如 `part_id >= 202512`）已通过 `partition_control` 配置自动生成，无需在 `extra_where_conditions` 中重复配置。

---

### variable_aliases（变量名别名映射）

用于处理模型变量名与数据库实际列名不一致的场景。

```yaml
variable_aliases:
  "cust_age": "age"
  "cust_income": "monthly_income"
  "score_risk": "risk_score"
```

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `variable_aliases` | `{}` | 变量名映射字典，键为模型变量名，值为数据库列名 | 当模型变量名与数据库列名不一致时配置 |

**工作原理**：

1. 模型中的变量名（如 `cust_age`）在元数据中找不到时，系统会检查 `variable_aliases`
2. 如果找到映射（`cust_age` → `age`），则在SQL生成时使用数据库列名 `age`
3. 元数据报告会同时显示原始变量名和映射后的数据库列名

**典型场景**：

- **场景1：模型变量名带前缀/后缀**
  ```yaml
  variable_aliases:
    "f_cust_age": "cust_age"
    "f_score_risk": "risk_score"
  ```

- **场景2：模型变量名使用缩写**
  ```yaml
  variable_aliases:
    "age": "cust_age"
    "inc": "monthly_income"
  ```

- **场景3：多模型共用变量表但变量名不同**
  ```yaml
  variable_aliases:
    "v1_cust_age": "cust_age"
    "v2_cust_age": "cust_age"
  ```

**注意事项**：
- `variable_aliases` 在 `variable_overrides` 之前应用，即先映射变量名，再检查覆盖配置
- 映射后的变量名仍需在元数据中存在对应的数据库列
- 元数据报告中的 `db_column_name` 列显示映射后的数据库列名
`
