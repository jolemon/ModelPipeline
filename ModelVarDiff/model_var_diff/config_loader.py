from dataclasses import dataclass, field
import json
import os
from typing import Literal, Optional

import pandas as pd


@dataclass
class VariableDef:
    name: str
    type: Literal["numeric", "enum"]
    data_source: str
    precision: Optional[int] = None


@dataclass
class TableMeta:
    user_key: str
    etldt: str
    sample_date: str
    sources: dict[str, str]


@dataclass
class Config:
    primary_keys: list[str]
    score_column: str
    variables: list[VariableDef]
    table_meta: Optional[TableMeta] = None


class ConfigLoader:
    # ── JSON 方式 ─────────────────────────────────────────────

    @staticmethod
    def load(path: str) -> Config:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "primary_keys" not in data:
            raise ValueError("Config missing 'primary_keys'")
        if "score_column" not in data:
            raise ValueError("Config missing 'score_column'")
        if "variables" not in data:
            raise ValueError("Config missing 'variables'")

        variables = []
        for v in data["variables"]:
            if "name" not in v or "data_source" not in v:
                raise ValueError(f"Variable entry missing required fields: {v}")
            var_type = v.get("type", "numeric")
            variables.append(VariableDef(
                name=v["name"].lower(),
                type=var_type,
                data_source=v["data_source"].lower(),
                precision=v.get("precision"),
            ))

        table_meta = None
        if "table_meta" in data:
            tm = data["table_meta"]
            sources = {k.lower(): v for k, v in tm.get("sources", {}).items()}
            table_meta = TableMeta(
                user_key=tm.get("user_key", "${user_key}"),
                etldt=tm.get("etldt", "${etldt}"),
                sample_date=tm.get("sample_date", "2026-06-27"),
                sources=sources,
            )

        return Config(
            primary_keys=[k.lower() for k in data["primary_keys"]],
            score_column=data["score_column"].lower(),
            variables=variables,
            table_meta=table_meta,
        )

    # ── 变量名列表方式 ─────────────────────────────────────────

    @staticmethod
    def from_var_list(var_list_path: str,
                      primary_keys: list[str],
                      score_column: str,
                      feature_warehouse_path: Optional[str] = None) -> Config:
        # 读取变量名
        var_names = ConfigLoader._read_var_names(var_list_path)

        # 尝试加载特征库
        warehouse = ConfigLoader._load_feature_warehouse(feature_warehouse_path)

        # 构建变量定义
        variables = []
        for name in var_names:
            data_source = ConfigLoader._lookup_source(warehouse, name)
            variables.append(VariableDef(
                name=name,
                type="numeric",
                data_source=data_source,
                precision=None,  # 从数据自动推断
            ))

        return Config(
            primary_keys=[k.lower() for k in primary_keys],
            score_column=score_column.lower(),
            variables=variables,
            table_meta=ConfigLoader._build_table_meta(warehouse),
        )

    # ── 模型文件方式 ────────────────────────────────────────────

    @staticmethod
    def from_model(model_path: str,
                   primary_keys: list[str],
                   score_column: str,
                   feature_warehouse_path: Optional[str] = None) -> Config:
        from shared.model_loaders import load_model as load_ml_model

        loader = load_ml_model(model_path)
        var_names = [n.lower() for n in loader.get_features()]
        print(f"  Model features: {len(var_names)}")

        warehouse = ConfigLoader._load_feature_warehouse(feature_warehouse_path)
        matched = 0
        variables = []
        for name in var_names:
            data_source = ConfigLoader._lookup_source(warehouse, name)
            if data_source != "unknown":
                matched += 1
            variables.append(VariableDef(
                name=name, type="numeric", data_source=data_source, precision=None,
            ))
        if warehouse is not None:
            print(f"  Feature warehouse matched: {matched}/{len(var_names)}")

        return Config(
            primary_keys=[k.lower() for k in primary_keys],
            score_column=score_column.lower(),
            variables=variables,
            table_meta=ConfigLoader._build_table_meta(warehouse),
        )

    # ── shared ──────────────────────────────────────────────────

    @staticmethod
    def _read_var_names(path: str) -> list[str]:
        names = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                names.append(line.lower())
        return names

    @staticmethod
    def _load_feature_warehouse(explicit_path: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Try to load feature warehouse from explicit path or model_library.config."""
        path = explicit_path
        if not path:
            try:
                from shared.model_library.config import feature_warehouse_path as fwp
                path = fwp
            except ImportError:
                pass
        if not path or not os.path.exists(path):
            return None

        # Load file
        if path.endswith(".xlsx") or path.endswith(".xls"):
            df = pd.read_excel(path)
        else:
            # Detect delimiter: if file starts with BOM or Chinese, try tab first
            df = pd.read_csv(path, sep="\t" if path.endswith(".csv") else None)

        if "字段名" not in df.columns:
            return None

        df["字段名"] = df["字段名"].astype(str).str.lower()

        # Resolve data_source column: prefer 来源表, else compose from 库名.表名
        if "来源表" in df.columns:
            pass  # already present
        elif "库名" in df.columns and "表名" in df.columns:
            df["来源表"] = df["库名"].astype(str) + "." + df["表名"].astype(str)
        else:
            return None

        return df

    @staticmethod
    def _lookup_source(warehouse: Optional[pd.DataFrame], var_name: str) -> str:
        if warehouse is not None:
            match = warehouse[warehouse["字段名"] == var_name.lower()]
            if len(match) > 0:
                return str(match.iloc[0]["来源表"])
        return "unknown"

    @staticmethod
    def _build_table_meta(warehouse: Optional[pd.DataFrame]) -> Optional[TableMeta]:
        """Build basic table_meta; sources = data_source name itself as table name."""
        return TableMeta(
            user_key="${user_key}",
            etldt="${etldt}",
            sample_date="2026-06-27",
            sources={},
        )

    # ── 通用 helpers ───────────────────────────────────────────

    @staticmethod
    def get_table_name(config: Config, data_source: str) -> str:
        if config.table_meta and data_source in config.table_meta.sources:
            return config.table_meta.sources[data_source]
        return data_source

    @staticmethod
    def get_user_key(config: Config) -> str:
        if config.table_meta:
            return config.table_meta.user_key
        return "${user_key}"

    @staticmethod
    def get_etldt(config: Config) -> str:
        if config.table_meta:
            return config.table_meta.etldt
        return "${etldt}"

    @staticmethod
    def get_sample_date(config: Config) -> str:
        if config.table_meta:
            return config.table_meta.sample_date
        return "2026-06-27"
