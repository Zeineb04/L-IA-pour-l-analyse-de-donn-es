"""Diagnostic d'une table DuckDB : complétude, types, doublons."""
import duckdb


def diagnose(con: duckdb.DuckDBPyConnection, table: str = "raw") -> dict:
    n_rows = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    described = con.execute(f'DESCRIBE "{table}"').fetchall()

    columns = []
    for c in described:
        name, dtype = c[0], c[1]
        q = f'"{name}"'
        nulls, distinct = con.execute(
            f'SELECT COUNT(*) - COUNT({q}), COUNT(DISTINCT {q}) FROM "{table}"'
        ).fetchone()
        columns.append({
            "name": name,
            "type": dtype,
            "null_pct": round(100 * nulls / n_rows, 1) if n_rows else 0.0,
            "distinct": distinct,
        })

    n_unique_rows = con.execute(
        f'SELECT COUNT(*) FROM (SELECT DISTINCT * FROM "{table}")'
    ).fetchone()[0]

    return {
        "table": table,
        "rows": n_rows,
        "cols": len(columns),
        "duplicates": n_rows - n_unique_rows,
        "columns": columns,
    }