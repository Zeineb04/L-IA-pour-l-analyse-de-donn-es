"""Chargement générique d'un fichier CSV/Excel dans DuckDB."""
import re
import unicodedata
from pathlib import Path

import duckdb


def normalize_name(name: str) -> str:
    """'Nom Station (kW)' -> 'nom_station_kw' : sans accents, espaces ni symboles."""
    name = name.replace("\ufeff", "")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    if not name:
        name = "col"
    if name[0].isdigit():
        name = "c_" + name
    return name


def _unique(names: list[str]) -> list[str]:
    seen, out = {}, []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}_{seen[n]}")
    return out


def load_dataset(path: str, con: duckdb.DuckDBPyConnection, table: str = "raw") -> str:
    """Charge un .csv/.xlsx dans DuckDB (table `table`) avec des noms de colonnes propres."""
    ext = Path(path).suffix.lower()
    if ext in (".csv", ".txt", ".tsv"):
        rel = con.read_csv(path)  # DuckDB détecte séparateur, BOM et types
    elif ext in (".xlsx", ".xls"):
        import pandas as pd
        rel = con.from_df(pd.read_excel(path))
    else:
        raise ValueError(f"Format non supporté : {ext}")
    new_cols = _unique([normalize_name(c) for c in rel.columns])
    rel = rel.project(", ".join(f'"{o}" AS "{n}"' for o, n in zip(rel.columns, new_cols)))
    con.execute(f'CREATE OR REPLACE TABLE "{table}" AS SELECT * FROM rel')
    return table