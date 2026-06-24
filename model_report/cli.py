import csv
import click
import pandas as pd
from model_report.config import ReportConfig
from model_report.interface import PickledScorecardAdapter
from model_report.generator import ReportGenerator


def _read_csv_auto_delim(path: str) -> pd.DataFrame:
    """Read CSV with auto-detected delimiter (comma or tab)."""
    with open(path, "r") as f:
        sample = f.read(8192)
    dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
    return pd.read_csv(path, sep=dialect.delimiter)


@click.command()
@click.option("--model", "-m", required=False, type=click.Path(exists=True),
              help="Optional path to .pkl scorecard file.")
@click.option("--data", "-d", required=True, type=click.Path(exists=True),
              help="Path to scoring result CSV file (comma or tab separated).")
@click.option("--output", "-o", default="./model_report.xlsx",
              type=click.Path(), help="Output Excel path.")
@click.option("--metadata", type=click.Path(exists=True),
              help="Optional variable metadata CSV/YAML.")
def main(model, data, output, metadata):
    """Generate a model report Excel from scorecard and scoring data.

    If --model is not provided, scorecard-dependent content (IV/KS from
    scorecard, WOE tables, scorecard detail) is skipped. Data-driven
    metrics are still computed.
    """
    report_config = ReportConfig()

    if model:
        scorecard = PickledScorecardAdapter(model)
    else:
        scorecard = None

    if data.endswith(".csv"):
        df = _read_csv_auto_delim(data)
    elif data.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data)
    else:
        raise click.BadParameter(f"Unsupported data format: {data}")

    generator = ReportGenerator(scorecard, report_config)
    generator.to_excel(output, df, metadata_path=metadata)
    click.echo(f"Report generated: {output}")


if __name__ == "__main__":
    main()
