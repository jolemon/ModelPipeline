import pytest
import tempfile
import pandas as pd
from pathlib import Path
from model_report.writer import ExcelWriter


class TestExcelWriter:
    @pytest.fixture
    def writer(self):
        return ExcelWriter()

    @pytest.fixture
    def sample_data(self):
        return {
            "样本分区分布": pd.DataFrame({
                "样本数据集划分标签": ["训练集", "测试集", "总计"],
                "样本分区": ["202501", "202501", ""],
                "好": [80, 35, 115],
                "坏": [20, 5, 25],
                "总数": [100, 40, 140],
                "坏占比": ["20.00%", "12.50%", "17.86%"],
            }),
            "样本建模分": pd.DataFrame({
                "样本数据集划分标签": ["训练集", "测试集", "跨时间验证集", "总计"],
                "好": [80, 35, 38, 153],
                "坏": [20, 5, 2, 27],
                "总数": [100, 40, 40, 180],
                "坏占比": ["20.00%", "12.50%", "5.00%", "15.00%"],
            }),
        }

    def test_write_creates_file(self, writer, sample_data):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            writer.write(output_path, {"模型设计": sample_data})
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0
        finally:
            Path(output_path).unlink()

    def test_write_sheet_names(self, writer, sample_data):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = f.name

        try:
            writer.write(output_path, {"模型设计": sample_data})
            import openpyxl
            wb = openpyxl.load_workbook(output_path)
            assert "模型设计" in wb.sheetnames
        finally:
            Path(output_path).unlink()
