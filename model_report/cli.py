import click
import pandas as pd
from model_report.config import ReportConfig
from model_report.interface import PickledScorecardAdapter
from model_report.generator import ReportGenerator


@click.command()
@click.option("--model", "-m", required=True, type=click.Path(exists=True),
              help="Path to .pkl scorecard file.")
@click.option("--data", "-d", required=True, type=click.Path(exists=True),
              help="Path to scoring result CSV file.")
@click.option("--output", "-o", default="./model_report.xlsx",
              type=click.Path(), help="Output Excel path.")
@click.option("--metadata", type=click.Path(exists=True),
              help="Optional variable metadata CSV/YAML.")
def main(model, data, output, metadata):
    """Generate a model report Excel from scorecard and scoring data."""
    report_config = ReportConfig()

    scorecard = PickledScorecardAdapter(model)

    if data.endswith(".csv"):
        df = pd.read_csv(data)
    elif data.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data)
    else:
        raise click.BadParameter(f"Unsupported data format: {data}")

    generator = ReportGenerator(scorecard, report_config)
    generator.to_excel(output, df, metadata_path=metadata)
    click.echo(f"Report generated: {output}")


if __name__ == "__main__":
    main()
