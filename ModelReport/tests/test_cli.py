import pytest
from click.testing import CliRunner
from model_report.cli import main


class TestCLI:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_cli_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--model" in result.output
        assert "--data" in result.output
        assert "--output" in result.output

    def test_cli_missing_required_args(self, runner):
        result = runner.invoke(main, [])
        assert result.exit_code != 0
