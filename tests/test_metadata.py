import pytest
import pandas as pd
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

    def test_feature_warehouse_xlsx(self):
        """Feature warehouse Excel with 字段名/字段含义/来源表 and auto-classification."""
        import tempfile
        df = pd.DataFrame({
            "字段名": ["txriskscorev7", "l3m_cnsmcnt_sum"],
            "字段含义": ["三方风险分", "近3个月总消费笔数"],
            "来源表": ["edap.table_risk", "wdyy.t_ccrdyyf_cust_cnsm_info_stats"],
        })
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            df.to_excel(f.name, index=False)
            tmp_path = f.name

        try:
            result = load_variable_metadata(tmp_path)
            assert result["txriskscorev7"]["变量解释含义"] == "三方风险分"
            assert result["txriskscorev7"]["来源"] == "edap.table_risk"
            assert "外部数据" in result["txriskscorev7"]["表描述"]  # edap.* → 外部数据
            assert result["l3m_cnsmcnt_sum"]["变量解释含义"] == "近3个月总消费笔数"
            assert "行为变量" in result["l3m_cnsmcnt_sum"]["表描述"]  # wdyy.t_ccrdyyf → 行为变量
            assert "字节" in result["l3m_cnsmcnt_sum"]["表描述"]      # platform
        finally:
            Path(tmp_path).unlink()
