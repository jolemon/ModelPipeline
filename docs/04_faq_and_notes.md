# lgb2sql 注意事项与常见问题

> 本文档包含使用注意事项、常见问题解答和联系方式。

---


**Q: 打分SQL输出中threshold/leaf_value信息重复出现，如何消除？**
A: 该信息来自模型决策树中阈值精度差异的调试输出，已优化为 `logging.debug()` 级别日志。默认情况下不会输出到控制台。如需查看调试信息，可配置Python日志级别：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Q: 项目有统一的日志配置文件吗？**
A: 当前项目未设置集中式日志配置，各模块使用Python标准库 `logging` 的默认行为。如需统一配置，建议在入口脚本（如 `run_full_pipeline.py`）中添加：
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
```

**Q: 关联计划摘要能否显示更多表名信息？**
A: 已支持。控制台输出和Markdown报告中现在会列出每个分组内的具体表名：
```
================================================================================
JOIN执行计划
================================================================================
分组数: 5
  组1: 外部数据/百融 (apply_no) - 1张表, 2个变量
    - edap_mrs.BRDT_APPLYLOANSTR
  组2: 征信变量-消金 (report_no) - 16张表, 20个变量
    - wdyy_mrs.T_PBCI_SUMMARY_OTHER
    - wdyy_mrs.T_PBCI_LIMIT_USE_OTHER
    ...
```

**Q: 变量匹配到多张表？**
A: 这是歧义变量，系统会按 `platform` → `behavior_platform_priority` 顺序自动选择。建议通过 `variable_overrides` 明确指定，或在 `config.yaml` 中配置 `platform` 指定首选平台。

**Q: 生成的SQL太长？**
A: 可以调整 `max_subquery_join` 参数（默认3），增大每个临时表内的JOIN数，减少临时表数量。或启用 `group_merge: true` 合并同一分组的临时表。

**Q: 如何只生成变量拼接SQL，不打分？**
A: 调用 `pipeline.run()` 时设置 `generate_score=False`。

**Q: 入模变量命中了黑名单，如何查看告警？**
A: 黑名单支持两种配置方式，合并生效：
1. **`blacklist_file`**：指定外部清单文件（如 `data/禁用变量清单.txt`），适合全局通用禁用变量
2. **`blacklist_vars`**：在 YAML 中直接列变量名，适合模型专属补充

任务流执行时会在元数据报告阶段输出醒目的告警信息，并在最终警告汇总中统计命中数量。关闭文件加载可将 `blacklist_file` 置空。

**Q: 如何实现时间区间匹配（如取申请前90天内的征信报告）？**
A: 在 `config.yaml` 的 `time_range_joins` 中配置表的时间区间匹配参数，支持 `DATEDIFF`（天数差）和 `MONTHS_BETWEEN`（月份差）两种时间函数。配置后该表会自动生成带 `ROW_NUMBER()` 去重的近因匹配SQL。详见【控制策略详解 → 策略四】。

**Q: 中征信等视图表如何配置（不通过 ci_rpt_id 桥接）？**
A: 中征信视图表（如 `jsbrpt.v_ods_02_all_zzxqsf_md5`）使用 `cert_no` 直接关联样本表，无需 `ci_rpt_id` 桥接。需要同时配置以下三项：
1. **`credit_platforms`**：将 `"中征信"` 加入征信平台列表，使系统识别为征信类变量
2. **`time_range_joins`**：配置时间区间匹配（如 `direction: "between"`、`dedup: true`）
3. **`partition_control.by_table`**：单独设置该表的分区策略

```yaml
sql_generation:
  credit_platforms:
    - "征信变量-消金"
    - "征信变量-总行"
    - "中征信"

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

partition_control:
  by_table:
    "jsbrpt.v_ods_02_all_zzxqsf_md5":
      strategy: "range"
      partition_field: "part_id"
      min_partition: "202408"
```
详见【控制策略详解 → 策略四】。

**Q: 时间区间匹配时变量表存在一对多（同一证件号多条记录）如何处理？**
A: 在 `time_range_joins` 中配置 `dedup: true`，系统会在子查询内使用 `ROW_NUMBER()` 按指定规则去重：
- `dedup_partition_by`：分区键（默认按样本关联键分区）
- `dedup_order_by`：排序规则（如 `"score_date DESC"` 取最新记录）
- `output_time_field`：输出去重后保留的时间字段别名

```yaml
time_range_joins:
  "your_table":
    match_mode: "range"
    dedup: true
    dedup_partition_by: "${sample_key}"
    dedup_order_by: "data_dt DESC"
    output_time_field: "formatted_data_dt"
```

**Q: 如何实现MD5转换关联（样本cert_no是MD5加密值）？**
A: 在 `config.yaml` 的 `custom_join_conditions` 中配置 `md5_transform: true`。例如：
```yaml
custom_join_conditions:
  by_table:
    "ads.ads_risk_$platform_cust_dz_indicator_ss":
      join_key: "cert_no"
      md5_transform: true
```
生成的SQL会自动处理 `s.cert_no = MD5(t.cert_no)`。详见【控制策略详解 → 策略五】。

**Q: 如何实现时间偏移关联（如申请时间减2天匹配数据日期）？**
A: 在 `custom_join_conditions` 中配置 `time_offset`：
```yaml
custom_join_conditions:
  by_table:
    "your_table":
      time_offset:
        field: "issue_time"
        offset_days: -2
        target_field: "data_dt"
        target_expr: "cast(to_char(to_date({field}, 'yyyyMMdd') - 2, 'yyyyMMdd') AS int)"
```
详见【控制策略详解 → 策略五】。

**Q: 如何为特定表添加额外的WHERE条件（如限定产品类型）？**
A: 在 `config.yaml` 的 `extra_where_conditions` 中配置：
```yaml
extra_where_conditions:
  by_table:
    "wdyy_mrs.T_CC_Cust_Crdt_Info_Stats":
      - "prd_sub_cls_cd IN ('MYJBV4')"
```
优先级：表 > 平台 > 分类。详见【控制策略详解 → 策略六】。


**Q: 如何控制不同分类的表使用不同的分区策略？**
A: 在 `partition_control` 中按分类配置：
```yaml
partition_control:
  by_category:
    "征信变量":
      strategy: "range"
      partition_field: "part_id"
      min_partition: "202512"
    "行为变量":
      strategy: "range"
      partition_field: "dt"
      min_partition: "202401"
```
详见【控制策略详解 → 策略一】。

**Q: 征信变量需要ci_rpt_id关联，但样本表只有cert_no怎么办？**
A: 启用 `credit_primary_table` 配置，系统会自动构建桥接表关联样本表（`cert_no`）与征信主键表（`ci_rpt_id`），再基于桥接表关联各征信变量表。支持MD5转换和时间窗口过滤。详见【控制策略详解 → 策略三】。

**Q: 表名中有 `$platform` 占位符如何配置？**
A: 在 `config.yaml` 中配置 `platform_value`：
```yaml
platform_value: "myjb"  # 借呗填myjb，月付填dyf，白条填rbt
```
系统会自动将 `$platform` 替换为对应值，如 `ads.ads_risk_$platform_cust_dz_indicator_ss` → `ads.ads_risk_myjb_cust_dz_indicator_ss`。

**Q: 模型变量名和数据库列名不一致怎么办？**
A: 在 `config.yaml` 的 `variable_aliases` 中配置变量名映射：
```yaml
variable_aliases:
  "model_var_name": "db_column_name"
  "f_cust_age": "cust_age"
```
系统会在SQL生成时自动使用数据库列名。详见【配置详解 → variable_aliases（变量名别名映射）】。

**Q: 如何运行测试验证配置是否正确？**
A: 执行统一测试入口：
```bash
python tests/test_all.py
```
包含24个单元测试，覆盖配置加载、元数据管理、SQL构建、模型解析、变量别名映射等核心功能。

**Q: 首次运行很慢，后续变快了？**
A: 这是正常的。首次加载 `metadata.yaml` 时会自动在同目录生成 `.pkl` 缓存文件，后续直接从缓存读取，速度提升约 **90 倍**（如 51s → 0.6s）。

**Q: 修改了 metadata.yaml 后缓存会更新吗？**
A: 会自动更新。系统会检测 YAML 文件的修改时间，如果比缓存文件新，会自动重新解析 YAML 并重建缓存。

**Q: 如何手动刷新缓存？**
A: 直接删除 `config/metadata.pkl` 文件，下次运行时会自动重新生成。
```bash
# 手动删除缓存
rm config/metadata.pkl
# Windows
# del config\metadata.pkl
```

**Q: 缓存文件可以提交到Git吗？**
A: 不建议。缓存文件是二进制格式且会根据 YAML 变化而重建，建议在 `.gitignore` 中排除：
```gitignore
config/*.pkl
```

**Q: 缓存加载失败会怎样？**
A: 会自动回退到原始 YAML 解析，不影响正常使用。可能的原因包括：缓存文件损坏、Python版本变更导致pickle不兼容等。

**Q: 如何验证生成的变量宽表数据质量？**
A: 使用项目内置的SQL验证工具，自动生成9维度验证SQL：
```bash
python scripts/analysis/generate_validation_sql.py \
    -m MYJBV4_ZY \
    -o tmp_01011939_20260429_MYJBV4_ZY_var_output \
    -s tmp_01011939_20260429_MYJBV4_ZY_sample
```
生成的验证SQL包含：样本量一致性、变量缺失率、高缺失率变量、数据波动、环比波动、主键唯一性、评分分布、评分区间、变量覆盖度。

**Q: SQL验证工具支持哪些数据库？**
A: 生成的SQL使用Hive/Spark SQL语法，兼容：
- Hive 2.x/3.x（`LATERAL VIEW EXPLODE`、`PERCENTILE_APPROX`、`STDDEV_POP`）
- Spark SQL（窗口函数、CTE）
- 如使用其他数据库，可能需要微调函数名（如 `PERCENTILE_APPROX` → `APPROX_PERCENTILE`）

**Q: 验证报告中的阈值建议是如何确定的？**
A: 阈值基于风控数据质量的一般经验值，仅供参考：
| 指标 | 建议阈值 | 说明 |
|------|---------|------|
| 样本量差异率 | ±0.1% | 允许LEFT JOIN导致的微量差异 |
| 核心变量缺失率 | < 10% | 关键风控变量应高覆盖 |
| 一般变量缺失率 | < 50% | 辅助变量允许一定缺失 |
| 跨月均值变化 | < ±20% | 业务稳定期数据波动范围 |
| 环比变化率 | < ±30% | 月度间正常波动 |
| 全空样本占比 | < 5% | 全空样本过多需排查数据源 |
| 评分P50 | 400-700 | 正常评分区间 |
实际阈值应根据业务特性和历史数据调整。

**Q: 高缺失率变量检测中 `LATERAL VIEW EXPLODE` 是什么语法？**
A: 这是Hive特有的行转列语法，用于将多个变量的缺失率统计结果从宽表格式转换为长表格式（每行一个变量）。如目标数据库不支持，可改用 `UNION ALL` 拼接多个 `SELECT`。
