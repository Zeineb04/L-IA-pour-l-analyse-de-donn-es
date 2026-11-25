"""Nettoyage générique : raw -> clean (la table raw n'est jamais modifiée)."""
import duckdb

NUMERIC = ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "FLOAT", "DOUBLE", "DECIMAL")


def clean_table(
    con: duckdb.DuckDBPyConnection,
    src: str = "raw",
    dst: str = "clean",
    drop_empty: bool = True,       # supprime les colonnes 100% vides
    drop_constant: bool = False,   # supprime les colonnes à valeur unique
    dedupe: bool = True,           # supprime les lignes dupliquées
    trim_strings: bool = True,     # espaces en trop, '' -> NULL
    impute: bool = False,          # médiane (numérique) / 'inconnu' (texte)
    impute_max_null_pct: float = 50.0,
    outliers: str | None = None,   # None, "null" ou "clip" (méthode IQR)
) -> dict:
    n_before = con.execute(f'SELECT COUNT(*) FROM "{src}"').fetchone()[0]
    cols = [(c[0], c[1]) for c in con.execute(f'DESCRIBE "{src}"').fetchall()]
    log, selects, dropped = [], [], []

    for name, dtype in cols:
        q = f'"{name}"'
        nulls, distinct = con.execute(
            f'SELECT COUNT(*) - COUNT({q}), COUNT(DISTINCT {q}) FROM "{src}"').fetchone()
        if drop_empty and nulls == n_before:
            dropped.append(f"{name} (vide)")
            continue
        if drop_constant and distinct <= 1:
            dropped.append(f"{name} (constante)")
            continue
        expr = q
        if trim_strings and dtype == "VARCHAR":
            expr = f"NULLIF(TRIM({q}), '')"
        is_num = dtype.startswith(NUMERIC)
        if outliers and is_num:
            q1, q3 = con.execute(
                f"SELECT quantile_cont({q}, 0.25), quantile_cont({q}, 0.75) FROM \"{src}\"").fetchone()
            if q1 is not None and q3 is not None and q3 > q1:
                lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
                n_out = con.execute(
                    f"SELECT COUNT(*) FROM \"{src}\" WHERE {q} < {lo} OR {q} > {hi}").fetchone()[0]
                if n_out:
                    if outliers == "clip":
                        expr = f"LEAST(GREATEST({q}, {lo}), {hi})"
                    else:
                        expr = f"CASE WHEN {q} BETWEEN {lo} AND {hi} THEN {q} END"
                    log.append(f"{name} : {n_out} valeurs aberrantes ({outliers})")
        if impute and 0 < nulls and 100 * nulls / n_before <= impute_max_null_pct:
            if is_num:
                expr = f"COALESCE({expr}, (SELECT MEDIAN({q}) FROM \"{src}\"))"
                log.append(f"{name} : {nulls} valeurs imputées (médiane)")
            elif dtype == "VARCHAR":
                expr = f"COALESCE({expr}, 'inconnu')"
                log.append(f"{name} : {nulls} valeurs imputées ('inconnu')")
        selects.append(f'{expr} AS "{name}"')

    distinct_kw = "DISTINCT " if dedupe else ""
    con.execute(f'CREATE OR REPLACE TABLE "{dst}" AS SELECT {distinct_kw}{", ".join(selects)} FROM "{src}"')
    n_after = con.execute(f'SELECT COUNT(*) FROM "{dst}"').fetchone()[0]
    if dropped:
        log.insert(0, f"{len(dropped)} colonnes supprimées : " + ", ".join(dropped))
    if n_before != n_after:
        log.append(f"{n_before - n_after} lignes dupliquées supprimées")
    return {"rows_before": n_before, "rows_after": n_after,
            "cols_before": len(cols), "cols_after": len(selects), "log": log}