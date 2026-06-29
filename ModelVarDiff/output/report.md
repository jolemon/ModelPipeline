# 模型变量对比报告

## 1. 输入数据概况

| 数据来源 | 行数 | 字段数 |
|----------|------|--------|
| 线上     | 1000 | 12 |
| 线下     | 1000 | 12 |
| 合并后 (inner join) | 1000 | - |

## 2. 分数校验结果

- **匹配数量**: 931/1000
- **匹配率**: 93.10%

## 3. 变量校验结果

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var10 | unknown | 2.50% | 2.10% | 769 | 1000 | 76.90% |
| var5 | unknown | 1.20% | 2.10% | 821 | 1000 | 82.10% |
| var8 | unknown | 2.20% | 0.80% | 843 | 1000 | 84.30% |
| var4 | unknown | 1.30% | 0.90% | 869 | 1000 | 86.90% |
| var7 | unknown | 1.30% | 1.10% | 890 | 1000 | 89.00% |
| var2 | unknown | 0.50% | 0.80% | 912 | 1000 | 91.20% |
| var6 | unknown | 0.20% | 0.50% | 940 | 1000 | 94.00% |
| var1 | unknown | 0.10% | 0.20% | 953 | 1000 | 95.30% |
| var3 | unknown | 0.00% | 0.00% | 960 | 1000 | 96.00% |
| var9 | unknown | 0.00% | 0.00% | 962 | 1000 | 96.20% |

## 4. 上钻分析（按数据源）

按匹配严格程度，依次展示 5 个维度的匹配率：

- **严格匹配**：该数据源下所有变量均匹配的行占比
- **75% 匹配**：至少 75% 变量匹配的行占比
- **50% 匹配**：至少 50% 变量匹配的行占比
- **25% 匹配**：至少 25% 变量匹配的行占比
- **宽松匹配**：任一变量匹配的行占比

| 数据源 | 变量数 | 严格匹配 | 75%匹配 | 50%匹配 | 25%匹配 | 宽松匹配 |
|--------|--------|----------|---------|---------|---------|----------|
| unknown | 10 | 30.70% | 91.70% | 100.00% | 100.00% | 100.00% |

## 5. 单变量分析

以下按匹配率从低到高，逐个分析所有未严格匹配（匹配率 < 100%）的变量。

### var10

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var10 | unknown | 4.30% | 4.10% | 769 | 1000 | 76.90% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 42 | 4.20% | `-10000.0`/`134.68`, `nan`/`217.18`, `nan`/`189.94` |
| 线上非空、线下空 | 40 | 4.00% | `116.82`/`nan`, `137.27`/`nan`, `197.24`/`-10000.0` |
| 线上非空、线下非空（取值不同） | 149 | 14.90% | `121.35`/`120.9`, `208.2`/`204.93`, `209.35`/`216.96` |

```sql
-- var10
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var10
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'10',
	'13',
	'154'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var10
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var10
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'45',
	'55',
	'72'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var10
-- 线上非空、线下非空（取值不同）的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var10
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'1',
	'3',
	'24'
)
ORDER BY ${user_key}, ${etldt}
;
```

---

### var5

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var5 | unknown | 3.20% | 4.10% | 821 | 1000 | 82.10% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 32 | 3.20% | `-10000.0`/`0.62`, `-10000.0`/`4.43`, `-10000.0`/`0.18` |
| 线上非空、线下空 | 41 | 4.10% | `6.58`/`-10000.0`, `0.17`/`nan`, `5.25`/`-10000.0` |
| 线上非空、线下非空（取值不同） | 106 | 10.60% | `0.02`/`0.23`, `4.33`/`4.18`, `4.27`/`5.01` |

```sql
-- var5
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var5
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'5',
	'72',
	'76'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var5
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var5
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'23',
	'26',
	'48'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var5
-- 线上非空、线下非空（取值不同）的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var5
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'6',
	'16',
	'29'
)
ORDER BY ${user_key}, ${etldt}
;
```

---

### var8

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var8 | unknown | 4.10% | 2.80% | 843 | 1000 | 84.30% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 41 | 4.10% | `-10000.0`/`100.245`, `nan`/`101.234`, `nan`/`103.096` |
| 线上非空、线下空 | 28 | 2.80% | `100.214`/`nan`, `102.226`/`nan`, `98.859`/`-10000.0` |
| 线上非空、线下非空（取值不同） | 88 | 8.80% | `100.107`/`95.496`, `100.211`/`98.673`, `97.288`/`118.027` |

```sql
-- var8
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var8
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'4',
	'56',
	'90'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var8
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var8
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'5',
	'48',
	'52'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var8
-- 线上非空、线下非空（取值不同）的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var8
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'10',
	'15',
	'22'
)
ORDER BY ${user_key}, ${etldt}
;
```

---

### var4

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var4 | unknown | 3.20% | 2.90% | 869 | 1000 | 86.90% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 30 | 3.00% | `-10000.0`/`10.016`, `-10000.0`/`10.136`, `nan`/`9.399` |
| 线上非空、线下空 | 27 | 2.70% | `10.052`/`-10000.0`, `8.389`/`nan`, `9.652`/`nan` |
| 线上非空、线下非空（取值不同） | 74 | 7.40% | `10.009`/`10.047`, `8.784`/`8.61`, `8.66`/`5.369` |

```sql
-- var4
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var4
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'176',
	'187',
	'194'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var4
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var4
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'20',
	'36',
	'75'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var4
-- 线上非空、线下非空（取值不同）的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var4
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'12',
	'15',
	'50'
)
ORDER BY ${user_key}, ${etldt}
;
```

---

### var7

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var7 | unknown | 3.30% | 3.10% | 890 | 1000 | 89.00% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 30 | 3.00% | `-10000.0`/`-0.5592`, `-10000.0`/`-2.9008`, `nan`/`7.4398` |
| 线上非空、线下空 | 28 | 2.80% | `-0.1021`/`-10000.0`, `-0.6111`/`nan`, `8.1109`/`-10000.0` |
| 线上非空、线下非空（取值不同） | 52 | 5.20% | `-0.103`/`0.0044`, `-0.1386`/`-0.1323`, `0.401`/`0.3793` |

```sql
-- var7
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var7
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'22',
	'48',
	'77'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var7
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var7
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'12',
	'25',
	'39'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var7
-- 线上非空、线下非空（取值不同）的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var7
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'7',
	'52',
	'56'
)
ORDER BY ${user_key}, ${etldt}
;
```

---

### var2

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var2 | unknown | 2.50% | 2.80% | 912 | 1000 | 91.20% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 25 | 2.50% | `-10000.0`/`0.5881`, `-10000.0`/`1.0119`, `nan`/`1.1842` |
| 线上非空、线下空 | 28 | 2.80% | `0.1249`/`-10000.0`, `0.5206`/`-10000.0`, `1.6642`/`-10000.0` |
| 线上非空、线下非空（取值不同） | 35 | 3.50% | `0.4237`/`0.4107`, `1.1358`/`1.1058`, `1.008`/`1.0445` |

```sql
-- var2
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var2
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'15',
	'22',
	'67'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var2
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var2
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'16',
	'96',
	'128'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var2
-- 线上非空、线下非空（取值不同）的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var2
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'47',
	'65',
	'95'
)
ORDER BY ${user_key}, ${etldt}
;
```

---

### var6

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var6 | unknown | 2.20% | 2.50% | 940 | 1000 | 94.00% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 22 | 2.20% | `-10000.0`/`38.78434`, `-10000.0`/`41.27615`, `nan`/`46.22764` |
| 线上非空、线下空 | 25 | 2.50% | `34.91627`/`-10000.0`, `53.57142`/`-10000.0`, `69.98289`/`-10000.0` |
| 线上非空、线下非空（取值不同） | 13 | 1.30% | `39.51572`/`40.49223`, `45.73698`/`32.1053`, `46.1734`/`42.12218` |

```sql
-- var6
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var6
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'79',
	'91',
	'154'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var6
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var6
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'39',
	'54',
	'115'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var6
-- 线上非空、线下非空（取值不同）的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var6
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'9',
	'36',
	'72'
)
ORDER BY ${user_key}, ${etldt}
;
```

---

### var1

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var1 | unknown | 2.10% | 2.20% | 953 | 1000 | 95.30% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 20 | 2.00% | `-10000.0`/`0.313815`, `-10000.0`/`0.338013`, `-10000.0`/`0.577734` |
| 线上非空、线下空 | 21 | 2.10% | `0.243526`/`-10000.0`, `0.523288`/`-10000.0`, `0.624967`/`-10000.0` |
| 线上非空、线下非空（取值不同） | 6 | 0.60% | `0.368317`/`0.338785`, `0.403791`/`0.236173`, `0.468209`/`0.467516` |

```sql
-- var1
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var1
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'1',
	'38',
	'45'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var1
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var1
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'4',
	'71',
	'175'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var1
-- 线上非空、线下非空（取值不同）的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var1
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'180',
	'470',
	'614'
)
ORDER BY ${user_key}, ${etldt}
;
```

---

### var3

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var3 | unknown | 2.00% | 2.00% | 960 | 1000 | 96.00% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 20 | 2.00% | `-10000.0`/`12.818207`, `-10000.0`/`19.748205`, `-10000.0`/`93.706272` |
| 线上非空、线下空 | 20 | 2.00% | `14.128927`/`-10000.0`, `16.599291`/`-10000.0`, `98.127652`/`-10000.0` |
| 线上非空、线下非空（取值不同） | 0 | 0.00% | - |

```sql
-- var3
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var3
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'18',
	'50',
	'112'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var3
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var3
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'3',
	'36',
	'55'
)
ORDER BY ${user_key}, ${etldt}
;
```

---

### var9

| 变量 | 所属数据源 | 线上缺失率 | 线下缺失率 | 匹配数 | 总数 | 匹配率 |
|------|------------|------------|------------|--------|------|--------|
| var9 | unknown | 2.00% | 2.00% | 962 | 1000 | 96.20% |

**按空值维度统计：**

| 线上变量取值 | 线下变量取值 | 个数 | 占比 | Top3 典型取值对（线上/线下） |
|--------------|--------------|------|------|------------------------------|
| 线上空、线下非空 | 19 | 1.90% | `-10000.0`/`0.355757`, `-10000.0`/`1.199924`, `-10000.0`/`1.855532` |
| 线上非空、线下空 | 19 | 1.90% | `0.506095`/`-10000.0`, `1.018266`/`-10000.0`, `2.20847`/`-10000.0` |
| 线上非空、线下非空（取值不同） | 0 | 0.00% | - |

```sql
-- var9
-- 线上空、线下非空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var9
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'45',
	'88',
	'89'
)
ORDER BY ${user_key}, ${etldt}
;
```

```sql
-- var9
-- 线上非空、线下空的3条样例
SELECT ${user_key} AS cert_no
     , ${etldt} AS etldt
     , var9
     , datediff(To_date('2026-06-27'), To_date(${etldt})) AS days_diff
FROM unknown
WHERE ${user_key} IN (
	'58',
	'173',
	'188'
)
ORDER BY ${user_key}, ${etldt}
;
```

---


# 校验规则

## 空值判定

以下情况视为「空值」：

- 单元格为空（NaN / 空字符串）
- 取值 < -9999（业务哨兵值）

**比较策略**：先判定空值，再比较取值。双方均为空值 → 匹配一致；一方为空一方非空 → 不一致。

## 模型分比较

差值绝对值 < 1e-3 视为匹配一致。

## 变量比较

| 变量类型 | 比较策略 |
|----------|----------|
| 枚举型 | 去空格后直接字符串比较（大小写敏感） |
| 数值型 | 取配置中指定精度（或自动推断的较高精度），将双方四舍五入到相同精度后比较 |
