import pytest
import pandas as pd
import numpy as np
from model_report.interface import ScorecardProtocol, PickledScorecardAdapter


class TestPickledScorecardAdapter:
    def test_adapter_creates_from_mock(self, mock_scorecard):
        """Verify adapter can wrap any object that matches protocol."""
        assert hasattr(mock_scorecard, "get_var_names")
        assert hasattr(mock_scorecard, "get_woe_table")
        assert hasattr(mock_scorecard, "get_iv_table")
        assert hasattr(mock_scorecard, "get_model_summary")
        assert hasattr(mock_scorecard, "get_scorecard")

    def test_adapter_not_implemented(self):
        """PickledScorecardAdapter requires actual .pkl file, test error."""
        with pytest.raises(FileNotFoundError):
            PickledScorecardAdapter("nonexistent_file.pkl")
