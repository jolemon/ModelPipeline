# 部署与使用指南

## 一、打包

### 前提

```bash
pip install build
```

### 构建 .whl

```bash
cd ModelReport
python3 -m build --wheel
```

产物位于 `dist/model_report-0.1.0-py3-none-any.whl`（约 20KB）。

---

## 二、部署

### 方式 A：pip 安装 .whl 文件

```bash
# 将 .whl 拷贝到目标机器后
pip install dist/model_report-0.1.0-py3-none-any.whl
```

安装后 CLI 命令 `model-report` 可用：

```bash
model-report --help
```

### 方式 B：pip 可编辑安装（开发模式）

```bash
pip install -e .
```

修改源码后即时生效，无需重新安装。

### 方式 C：直接使用（无需安装）

在项目根目录下运行，确保依赖已安装：

```bash
pip install -r requirements.txt
python3 -m model_report --data test.csv
```

---

## 三、依赖

### 核心依赖（必需）

| 包 | 版本 | 用途 |
|---|------|------|
| pandas | ≥1.5.0 | 数据处理 |
| numpy | ≥1.24.0 | 数值计算 |
| scipy | ≥1.10.0 | KS 检验 |
| scikit-learn | ≥1.2.0 | AUC / ROC |
| toad | ≥0.1.0 | IV 计算 |
| openpyxl | ≥3.1.0 | Excel 写入 |
| click | ≥8.1.0 | CLI |

### 可选依赖

| 包 | 用途 |
|---|------|
| statsmodels | 仅在使用 `.pkl` 评分卡时需要（`scorecard_jsb.py` 依赖） |
| pytest | 仅开发/测试时需要 |

### 一键安装

```bash
# 仅运行时依赖
pip install model_report-0.1.0-py3-none-any.whl

# 含测试依赖
pip install model_report-0.1.0-py3-none-any.whl[dev]
```

---

## 四、部署后验证

### 1. 验证 CLI 可用

```bash
model-report --help
```

预期输出：

```
Usage: model-report [OPTIONS]

  Generate a model report Excel from scorecard and scoring data.
  ...

Options:
  -m, --model PATH     Optional path to .pkl scorecard file.
  -d, --data PATH      Path to scoring result CSV file.  [required]
  -o, --output PATH    Output Excel path.
  --metadata PATH      Optional variable metadata CSV/YAML.
  --help               Show this message and exit.
```

### 2. 生成第一份报告

```bash
model-report -d test.csv -o test_report.xlsx
```

### 3. 运行测试（开发环境）

```bash
pytest tests/ -v
```

预期：85 passed。

---

## 五、环境要求

| 项 | 要求 |
|---|------|
| Python | ≥ 3.9 |
| 操作系统 | Linux / macOS / Windows |
| 磁盘空间 | < 10 MB（不含依赖） |
| 内存 | 取决于数据量，500 样本约需 200MB |

---

## 六、常见部署问题

### Q: `pip install` 报 `No module named 'setuptools'`

```bash
pip install --upgrade pip setuptools wheel
```

### Q: `pip install` 报 `ModuleNotFoundError: statsmodels`

statsmodels 是可选依赖。如果不需要加载 `.pkl` 评分卡文件，可以忽略。如果需要，手动安装：

```bash
pip install statsmodels
```

### Q: 生产环境无外网，如何安装依赖？

```bash
# 在有网络的机器上下载所有依赖
pip download model_report-0.1.0-py3-none-any.whl -d ./offline_packages

# 拷贝到生产机器后离线安装
pip install model_report-0.1.0-py3-none-any.whl \
  --no-index \
  --find-links ./offline_packages
```

### Q: 如何嵌入到已有的 Python 项目中？

```python
# 安装后直接 import
from model_report import ReportGenerator, ReportConfig

gen = ReportGenerator()
gen.to_excel("output.xlsx", your_dataframe)
```

### Q: toad 安装失败（ARM Mac / Linux）？

toad 在某些平台上需要编译。如果安装失败，可以单独处理 IV 计算的降级方案：

```python
# 不依赖 toad 的替代：使用 compute_woe_table 计算 WOE 表
# （已在 model_report 内部使用，无需额外配置）
```

---

## 七、版本升级

```bash
pip install --upgrade model_report-0.2.0-py3-none-any.whl
```

升级后验证：

```bash
model-report --help
pytest tests/ -v
```
