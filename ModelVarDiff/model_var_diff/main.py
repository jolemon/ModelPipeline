import argparse
import sys

import pandas as pd

from .config_loader import ConfigLoader, Config
from .comparator import Comparator
from .analyzer import Analyzer
from .report_generator import ReportGenerator


def _build_config(args) -> Config:
    """Build Config from --config / --var-list / --model (mutually exclusive)."""
    config_sources = [args.config, args.var_list, args.model]
    if sum(1 for s in config_sources if s) > 1:
        print("ERROR: use only one of --config, --var-list, --model")
        sys.exit(1)

    score_col = args.score_online or args.score
    fw = getattr(args, "feature_warehouse", None)

    if args.config:
        print(f"Loading config from {args.config}...")
        return ConfigLoader.load(args.config)

    if args.var_list:
        print(f"Loading variable list from {args.var_list}...")
        return ConfigLoader.from_var_list(
            var_list_path=args.var_list,
            primary_keys=args.pk,
            score_column=score_col,
            feature_warehouse_path=fw,
        )

    if args.model:
        print(f"Loading model from {args.model}...")
        return ConfigLoader.from_model(
            model_path=args.model,
            primary_keys=args.pk,
            score_column=score_col,
            feature_warehouse_path=fw,
        )

    print("ERROR: must specify --config, --var-list, or --model")
    sys.exit(1)


def _resolve_score_columns(args, config: Config) -> tuple[str, str]:
    """Return (online_score_col, offline_score_col) after optional rename."""
    online_col = config.score_column
    offline_col = args.score_offline or args.score_online or online_col
    return online_col, offline_col


def main():
    parser = argparse.ArgumentParser(description="Model Variable Comparison Tool")

    # Config source (mutually exclusive in practice)
    parser.add_argument("--config", default=None, help="Path to variables.json config")
    parser.add_argument("--var-list", default=None, help="Path to variable name list (.txt)")
    parser.add_argument("--model", default=None, help="Path to model file (.model / .pkl / .pmml)")

    # Data I/O
    parser.add_argument("--online", required=True, help="Path to online CSV file")
    parser.add_argument("--offline", required=True, help="Path to offline CSV file")
    parser.add_argument("--output", default="output", help="Output directory (default: output)")
    parser.add_argument("--sep", default=",", help="CSV delimiter (default: comma. Use $'\\t' for tab)")

    # Options for --var-list mode
    parser.add_argument("--pk", nargs="+", default=["user_id"],
                        help="Primary key column(s) (default: user_id)")
    parser.add_argument("--score", default="model_score",
                        help="Score column name, same for both files (default: model_score)")
    parser.add_argument("--score-online", default=None,
                        help="Online score column name (overrides --score)")
    parser.add_argument("--score-offline", default=None,
                        help="Offline score column name (overrides --score)")
    parser.add_argument("--feature-warehouse", default=None,
                        help="Path to feature warehouse Excel (optional)")

    args = parser.parse_args()

    # Build config (--config reads JSON; --var-list builds from CLI args)
    config = _build_config(args)

    # Resolve actual score column names for both files
    score_online, score_offline = _resolve_score_columns(args, config)
    if score_offline != config.score_column:
        config.score_column = score_offline  # config uses the offline name for now
        # Wait — we need the online name as canonical. Flip.
        config.score_column = score_online

    print(f"  Primary keys: {config.primary_keys}")
    print(f"  Score columns: online='{score_online}'  offline='{score_offline}'")
    print(f"  Variables: {len(config.variables)}")

    # Read CSVs with specified delimiter; normalize column names to lowercase
    print(f"\nReading online data from {args.online}...")
    df_online = pd.read_csv(args.online, sep=args.sep)
    df_online.columns = df_online.columns.str.lower()
    print(f"  Online rows: {len(df_online)}, columns: {len(df_online.columns)}")

    print(f"Reading offline data from {args.offline}...")
    df_offline = pd.read_csv(args.offline, sep=args.sep)
    df_offline.columns = df_offline.columns.str.lower()
    print(f"  Offline rows: {len(df_offline)}, columns: {len(df_offline.columns)}")

    # Normalize score column names to lowercase for matching
    score_online = score_online.lower()
    score_offline = score_offline.lower()

    # Align score column names: rename offline to match online if different
    if score_offline != score_online:
        if score_offline not in df_offline.columns:
            print(f"ERROR: Score column '{score_offline}' not found in offline CSV")
            sys.exit(1)
        df_offline = df_offline.rename(columns={score_offline: score_online})
        print(f"  Renamed offline score '{score_offline}' -> '{score_online}'")

    # Validate columns
    all_vars = config.primary_keys + [score_online] + [v.name for v in config.variables]
    for col in all_vars:
        if col not in df_online.columns:
            print(f"ERROR: Column '{col}' not found in online CSV")
            sys.exit(1)
        if col not in df_offline.columns:
            print(f"ERROR: Column '{col}' not found in offline CSV")
            sys.exit(1)

    # Merge on primary keys
    print(f"\nMerging on primary keys: {config.primary_keys}...")
    merged = pd.merge(
        df_online, df_offline,
        on=config.primary_keys,
        suffixes=("_online", "_offline"),
        how="inner",
    )
    print(f"  Merged rows: {len(merged)}")

    if len(merged) == 0:
        print("ERROR: No matching rows after merge. Check primary keys.")
        sys.exit(1)

    # Run comparison
    print("\nRunning comparison...")
    comparator = Comparator(merged, config)
    results = comparator.compare_all()

    # Analyze
    print("Computing statistics...")
    analyzer = Analyzer(df_online, df_offline, merged, config, results)

    overview = analyzer.compute_overview()
    score_stats = analyzer.compute_score_stats()
    var_stats = analyzer.compute_variable_stats()
    drill_up_multi = analyzer.compute_drill_up_multi()

    # Print summary
    print(f"\nScore match rate: {score_stats.match_rate:.2%}")
    print("\nVariable match rates:")
    for v in var_stats:
        print(f"  {v.name}: {v.match_rate:.2%}")
    print("\nData source drill-up (strict → loose):")
    for r in drill_up_multi:
        print(f"  {r.data_source}: strict={r.strict:.2%}, 75%={r.match_75:.2%}, "
              f"50%={r.match_50:.2%}, 25%={r.match_25:.2%}, loose={r.loose:.2%}")

    # Per-variable anomaly analysis (Section 5)
    print("Computing per-variable analysis...")
    var_analyses = analyzer.compute_variable_analysis(var_stats)
    imperfect_count = len(var_analyses)
    print(f"  Variables with <100% match: {imperfect_count}")

    # Generate report
    print("Generating report...")
    report_gen = ReportGenerator(args.output, config)
    report_path = report_gen.generate(overview, score_stats, var_stats, drill_up_multi, var_analyses)
    print(f"\nReport written to: {report_path}")


if __name__ == "__main__":
    main()
