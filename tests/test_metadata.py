import pytest
import tempfile
from pathlib import Path
from model_report.metadata import load_variable_metadata


class TestLoadVariableMetadata:
    def test_load_csv_metadata(self):
        csv_content = "变量名,变量解释含义,来源,表描述\nfeat_a,近3个月消费笔数,wdyy.table_a,消费状态\nfeat_b,近24个月余额,wdyy.table_b,额度状态\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            tmp_path = f.name

        try:
            result = load_variable_metadata(tmp_path)
            assert result["feat_a"]["变量解释含义"] == "近3个月消费笔数"
            assert result["feat_a"]["来源"] == "wdyy.table_a"
            assert result["feat_b"]["表描述"] == "额度状态"
        finally:
            Path(tmp_path).unlink()

    def test_missing_file_returns_empty(self):
        result = load_variable_metadata("nonexistent.csv")
        assert result == {}

    def test_no_metadata_returns_empty_strings(self):
        result = load_variable_metadata(None)
        assert result == {}
