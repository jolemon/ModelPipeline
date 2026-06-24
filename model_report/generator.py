import os
from typing import Optional
import pandas as pd
from model_report.config import ReportConfig
from model_report.metadata import load_variable_metadata
from model_report.writer import ExcelWriter
from model_report.sheets.model_design import build_model_design_sheet
from model_report.sheets.variable_analysis import build_variable_analysis_sheet
from model_report.sheets.model_performance import build_model_performance_sheet

# Default feature warehouse paths (from model_library/config.py)
_DEFAULT_WAREHOUSE_DIR = "/srv/data_warehouse"
_DEFAULT_WAREHOUSE_FILES = [
    os.path.join(_DEFAULT_WAREHOUSE_DIR, "特征映射表.xlsx"),
    os.path.join(_DEFAULT_WAREHOUSE_DIR, "特征映射表_新底座.xlsx"),
]


def _resolve_metadata_path(explicit_path: Optional[str] = None) -> Optional[str]:
    """Resolve metadata file path: explicit > default warehouse > None."""
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path
    for default_path in _DEFAULT_WAREHOUSE_FILES:
        if os.path.exists(default_path):
            return default_path
    return explicit_path  # May be None or non-existent (handled by loader)


# ── Progress helpers ──

def _print_header(msg: str):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


def _log(msg: str):
    print(f"  {msg}")


def _step(i: int, total: int, desc: str):
    print(f"\n  [{i}/{total}] {desc}...", end="", flush=True)


def _ok():
    print(" ✓")


class ReportGenerator:
    """Orchestrates the three sheet builders and writes the Excel report."""

    def __init__(self, scorecard=None, config=None):
        self.scorecard = scorecard
        self.config = config if config is not None else ReportConfig()
        self._writer = ExcelWriter()
        self._metadata = {}

    def generate(self, data: pd.DataFrame, metadata_path=None) -> dict:
        """Generate all report sheets as structured data."""
        self._validate_data(data)

        _print_header("模型报告生成器 v1.0.0")
        n = len(data)
        train_n = (data[self.config.flag_col] == "train").sum()
        oot_n = (data[self.config.flag_col] == "oot").sum()
        _log(f"数据: {n:,} 样本 | train={train_n:,} oot={oot_n:,} | bad_rate={data[self.config.target_col].mean():.2%}")

        resolved = _resolve_metadata_path(metadata_path)
        if resolved:
            _log(f"元数据: {resolved}")
        self._metadata = load_variable_metadata(resolved)

        # ── Sheet 1 ──
        _step(1, 3, "模型设计 — 样本分区分布 + 建模分 + 效果汇总")
        sheet1 = build_model_design_sheet(data, self.config)
        _log(f"  分区分布: {len(sheet1.get('样本分区分布', []))} 行")
        _log(f"  建模分: {len(sheet1.get('样本建模分', []))} 行")
        _ok()

        # ── Sheet 2 ──
        _step(2, 3, "变量分析 — 指标总览 + WOE 分箱")
        sheet2 = build_variable_analysis_sheet(data, self.scorecard, self.config, self._metadata)
        n_vars = len(sheet2.get("变量总览", []))
        n_woe = len(sheet2.get("Top10 单变量 WOE 分箱分析", []))
        _log(f"  变量数: {n_vars} | WOE 分箱: {n_woe} 个")
        _ok()

        # ── Sheet 3 ──
        _step(3, 3, "模型表现 — 评分卡详情 + 效果 + 回溯 + 分箱")
        sheet3 = build_model_performance_sheet(data, self.scorecard, self.config)
        n_bin = len(sheet3.get("分箱表现", []))
        _log(f"  分箱表现: {n_bin} 个分区")
        _ok()

        _print_header("报告生成完成")
        return {
            self.config.sheet1_name: sheet1,
            self.config.sheet2_name: sheet2,
            self.config.sheet3_name: sheet3,
        }

    def to_excel(self, output_path: str, data: pd.DataFrame,
                 metadata_path=None) -> None:
        """Generate report and write to Excel file."""
        sheets = self.generate(data, metadata_path)
        _log(f"正在写入 Excel → {output_path}")
        self._writer.write(output_path, sheets)
        _print_header(f"已保存: {output_path}")

    def _validate_data(self, data: pd.DataFrame) -> None:
        """Validate that required columns exist."""
        required = [
            self.config.flag_col,
            self.config.target_col,
        ]

        missing = [col for col in required if col not in data.columns]
        if missing:
            raise ValueError(
                f"Missing required columns in data: {missing}. "
                f"Available columns: {list(data.columns)}"
            )

        # Warn if no score column found (not fatal)
        score_col = self.config.resolve_score_column(list(data.columns))
        if score_col not in data.columns:
            raise ValueError(
                f"No score column found. Tried '{self.config.sc_score_col}' "
                f"and '{self.config.score_col}'. "
                f"Available columns: {list(data.columns)}"
            )

        target_vals = data[self.config.target_col].dropna().unique()
        if set(target_vals) - {0, 1}:
            raise ValueError(
                f"Target column '{self.config.target_col}' must contain only 0 and 1, "
                f"found: {sorted(target_vals)}"
            )

        flag_vals = data[self.config.flag_col].unique()
        if "train" not in flag_vals:
            raise ValueError(
                f"Data must contain 'train' in '{self.config.flag_col}' column. "
                f"Found: {sorted(flag_vals)}"
            )
