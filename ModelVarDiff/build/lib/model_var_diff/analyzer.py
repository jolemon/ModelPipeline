from dataclasses import dataclass, field
import math

import pandas as pd

from .config_loader import Config, VariableDef
from .comparator import _is_null


@dataclass
class OverviewStats:
    online_rows: int
    offline_rows: int
    merged_rows: int
    online_cols: int
    offline_cols: int
    online_missing: dict[str, float]
    offline_missing: dict[str, float]


@dataclass
class MatchStats:
    match_count: int
    total: int
    match_rate: float


@dataclass
class VariableMatchStats:
    name: str
    match_count: int
    total: int
    match_rate: float
    data_source: str


@dataclass
class DrillUpRow:
    data_source: str
    var_count: int
    strict: float
    match_75: float
    match_50: float
    match_25: float
    loose: float


@dataclass
class AnomalyGroup:
    """Stats for one null-status category of a variable."""
    label: str                          # e.g. "线上空、线下非空"
    count: int
    pct: float
    top_pairs: list[tuple[str, str, int]]  # (online_val, offline_val, count)


@dataclass
class VariableAnalysis:
    """Per-variable anomaly breakdown for Section 5."""
    name: str
    data_source: str
    online_missing_rate: float
    offline_missing_rate: float
    match_count: int
    total: int
    match_rate: float
    anomaly_groups: list[AnomalyGroup]   # null-status breakdowns
    sql_samples: dict[str, list[dict]]   # category_label → list of sample rows


class Analyzer:
    def __init__(self, df_online: pd.DataFrame, df_offline: pd.DataFrame, merged: pd.DataFrame, config: Config,
                 results: dict[str, pd.Series]):
        self.df_online = df_online
        self.df_offline = df_offline
        self.merged = merged
        self.config = config
        self.results = results

    # ── helpers ──────────────────────────────────────────────────

    def _group_by_source(self) -> dict[str, list[str]]:
        source_vars: dict[str, list[str]] = {}
        for vardef in self.config.variables:
            source_vars.setdefault(vardef.data_source, []).append(vardef.name)
        return source_vars

    def _source_rates(self) -> dict[str, float]:
        source_vars = self._group_by_source()
        rates = {}
        for source, var_names in source_vars.items():
            all_match = pd.Series(True, index=self.merged.index)
            for name in var_names:
                all_match = all_match & self.results[name]
            rates[source] = float(all_match.mean())
        return rates

    def _per_row_match_counts(self, var_names: list[str]) -> pd.Series:
        count = pd.Series(0, index=self.merged.index, dtype=int)
        for name in var_names:
            count += self.results[name].astype(int)
        return count

    # ── public methods ───────────────────────────────────────────

    def compute_overview(self) -> OverviewStats:
        online_missing = {}
        for col in self.df_online.columns:
            online_missing[col] = self.df_online[col].isna().mean()

        offline_missing = {}
        for col in self.df_offline.columns:
            offline_missing[col] = self.df_offline[col].isna().mean()

        return OverviewStats(
            online_rows=len(self.df_online),
            offline_rows=len(self.df_offline),
            merged_rows=len(self.merged),
            online_cols=len(self.df_online.columns),
            offline_cols=len(self.df_offline.columns),
            online_missing=online_missing,
            offline_missing=offline_missing,
        )

    def compute_score_stats(self) -> MatchStats:
        s = self.results["score"]
        return MatchStats(
            match_count=int(s.sum()),
            total=len(s),
            match_rate=float(s.mean()),
        )

    def compute_variable_stats(self) -> list[VariableMatchStats]:
        source_rates = self._source_rates()
        stats = []
        for vardef in self.config.variables:
            s = self.results[vardef.name]
            stats.append(VariableMatchStats(
                name=vardef.name,
                match_count=int(s.sum()),
                total=len(s),
                match_rate=float(s.mean()),
                data_source=vardef.data_source,
            ))
        # Sort: source rate ascending → variable rate ascending
        stats.sort(key=lambda x: (source_rates.get(x.data_source, 0), x.match_rate))
        return stats

    def compute_drill_up(self) -> dict[str, MatchStats]:
        source_vars = self._group_by_source()
        total = len(self.merged)
        drill_up = {}
        for source, var_names in source_vars.items():
            all_match = pd.Series(True, index=self.merged.index)
            for name in var_names:
                all_match = all_match & self.results[name]
            drill_up[source] = MatchStats(
                match_count=int(all_match.sum()),
                total=total,
                match_rate=float(all_match.mean()),
            )
        return drill_up

    def compute_drill_up_multi(self) -> list[DrillUpRow]:
        source_vars = self._group_by_source()
        total = len(self.merged)
        rows = []
        for source, var_names in source_vars.items():
            n = len(var_names)
            counts = self._per_row_match_counts(var_names)
            rows.append(DrillUpRow(
                data_source=source,
                var_count=n,
                strict=float((counts >= n).mean()),
                match_75=float((counts >= math.ceil(n * 0.75)).mean()),
                match_50=float((counts >= math.ceil(n * 0.50)).mean()),
                match_25=float((counts >= math.ceil(n * 0.25)).mean()),
                loose=float((counts >= 1).mean()),
            ))
        rows.sort(key=lambda r: r.strict)
        return rows

    # ── Section 5: per-variable anomaly analysis ─────────────────

    def compute_variable_analysis(self, var_stats: list[VariableMatchStats]) -> list[VariableAnalysis]:
        """For each variable with match rate < 100%, produce an anomaly breakdown."""
        results: list[VariableAnalysis] = []
        # Only analyze non-perfect variables. Sort: source rate → variable rate
        source_rates = self._source_rates()
        imperfect = [v for v in var_stats if v.match_rate < 1.0]
        imperfect.sort(key=lambda x: (source_rates.get(x.data_source, 0), x.match_rate))

        for vs in imperfect:
            name = vs.name
            online_col = self.merged[f"{name}_online"]
            offline_col = self.merged[f"{name}_offline"]

            online_null = _is_null(online_col)
            offline_null = _is_null(offline_col)
            matched = self.results[name]

            total = len(self.merged)

            # ── Null-status breakdown ──────────────────────────────
            # Category 1: online null, offline not null (and not matched)
            cat1_mask = online_null & ~offline_null
            # Category 2: online not null, offline null
            cat2_mask = ~online_null & offline_null
            # Category 3: both not null but values differ
            cat3_mask = ~online_null & ~offline_null & ~matched

            groups = []
            sql_samples: dict[str, list[dict]] = {}

            for label, mask in [
                ("线上空、线下非空", cat1_mask),
                ("线上非空、线下空", cat2_mask),
                ("线上非空、线下非空（取值不同）", cat3_mask),
            ]:
                count = int(mask.sum())
                pct = count / total if total > 0 else 0.0
                pairs = self._top_value_pairs(online_col, offline_col, mask)
                groups.append(AnomalyGroup(label=label, count=count, pct=pct, top_pairs=pairs))
                sql_samples[label] = self._sample_rows(name, mask)

            results.append(VariableAnalysis(
                name=name,
                data_source=vs.data_source,
                online_missing_rate=online_null.mean(),
                offline_missing_rate=offline_null.mean(),
                match_count=vs.match_count,
                total=vs.total,
                match_rate=vs.match_rate,
                anomaly_groups=groups,
                sql_samples=sql_samples,
            ))

        return results

    def _top_value_pairs(self, online_col: pd.Series, offline_col: pd.Series,
                         mask: pd.Series) -> list[tuple[str, str, int]]:
        """Return top 3 most frequent (online_val, offline_val) pairs on masked rows."""
        sub = pd.DataFrame({"o": online_col[mask].astype(str), "f": offline_col[mask].astype(str)})
        if len(sub) == 0:
            return []
        counts = sub.groupby(["o", "f"]).size().sort_values(ascending=False)
        return [(o, f, int(c)) for (o, f), c in counts.head(3).items()]

    def _sample_rows(self, var_name: str, mask: pd.Series) -> list[dict]:
        """Extract up to 3 sample rows for SQL generation."""
        indices = mask[mask].index[:3]
        samples = []
        for idx in indices:
            row = {}
            for pk in self.config.primary_keys:
                # After merge, pk is stored as pk_online; both sides are identical (inner join)
                col = f"{pk}_online" if f"{pk}_online" in self.merged.columns else pk
                row[pk] = str(self.merged.loc[idx, col])
            row[f"{var_name}_online"] = str(self.merged.loc[idx, f"{var_name}_online"])
            row[f"{var_name}_offline"] = str(self.merged.loc[idx, f"{var_name}_offline"])
            samples.append(row)
        return samples
