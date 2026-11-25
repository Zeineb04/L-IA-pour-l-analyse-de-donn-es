"""Diagnostic générique d'une table DuckDB (aucune colonne codée en dur)."""
import duckdb

NUMERIC = ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "FLOAT", "DOUBLE", "DECIMAL")


def profile_table(con: duckdb.DuckDBPyConnection, table: str = "raw") -> dict:
    n_rows = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    n_dup = n_rows - con.execute(f'SELECT COUNT(*) FROM (SELECT DISTINCT * FROM "{table}")').fetchone()[0]
    cols = con.execute(f'DESCRIBE "{table}"').fetchall()
    report = []
    for name, dtype, *_ in cols:
        nulls, distinct = con.execute(
            f'SELECT COUNT(*) - COUNT("{name}"), COUNT(DISTINCT "{name}") FROM "{table}"'
        ).fetchone()
        info = {
            "column": name, "type": dtype, "nulls": nulls,
            "null_pct": round(100 * nulls / n_rows, 1) if n_rows else 0.0,
            "distinct": distinct,
        }
        if dtype.startswith(NUMERIC):
            info["min"], info["max"], info["mean"] = con.execute(
                f'SELECT MIN("{name}"), MAX("{name}"), ROUND(AVG("{name}"), 2) FROM "{table}"'
            ).fetchone()
        report.append(info)
    issues = []
    if n_dup:
        issues.append(f"{n_dup} lignes dupliquées")
    for c in report:
        if c["null_pct"] == 100:
            issues.append(f"{c['column']} : colonne entièrement vide")
        elif c["null_pct"] >= 50:
            issues.append(f"{c['column']} : {c['null_pct']}% de valeurs manquantes")
        elif c["distinct"] == 1:
            issues.append(f"{c['column']} : valeur constante")
    return {"rows": n_rows, "columns": len(cols), "duplicates": n_dup,
            "details": report, "issues": issues}