
import re
import ollama
import duckdb
from src.sql.validator import is_safe_sql


SYSTEM_PROMPT = """Tu es un expert SQL pour DuckDB.
Tu dois répondre UNIQUEMENT avec une requête SQL SELECT valide.
N'écris aucun texte avant ou après la requête.
N'utilise jamais DROP, DELETE, UPDATE, INSERT, CREATE, ALTER, COPY, ATTACH.
Utilise UNIQUEMENT le nom de table et les colonnes fournis.

Règles importantes :
- Une ligne de la table = un enregistrement (ex : un point de charge). Pour compter
  des enregistrements, utilise COUNT(*).
- Pour compter des entités uniques (ex : des stations), utilise COUNT(DISTINCT colonne_identifiant).
  Une colonne d'identifiant a un nombre de valeurs distinctes inférieur au nombre de lignes
  quand l'entité apparaît sur plusieurs lignes.
- Une colonne qui contient un total propre à un groupe répété sur chaque ligne du groupe
  (ex : nbre_pdc = nombre de points de charge de la station) ne doit JAMAIS être additionnée
  avec SUM ou AVG. Utilise COUNT(*), ou MAX par groupe.
- Pour un classement d'entités (top N), utilise GROUP BY pour qu'une entité n'apparaisse
  qu'une seule fois, puis ORDER BY ... DESC LIMIT N.
  Exemples :
Question : Combien y a-t-il d'enregistrements au total ?
SQL : SELECT COUNT(*) FROM clean

"""


def get_schema(con, table: str = "clean") -> str:
    """Retourne le schéma (avec nombre de valeurs distinctes) + 3 lignes d'exemple."""
    n_rows = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    cols = con.execute(f'DESCRIBE "{table}"').fetchall()
    schema_lines = []
    id_cols = []
    for c in cols:
        name = c[0]
        distinct = con.execute(
            f'SELECT COUNT(DISTINCT "{name}") FROM "{table}"'
        ).fetchone()[0]
        line = f"- {name} ({c[1]}, {distinct} valeurs distinctes)"
        # Colonne d'identifiant dont les valeurs se répètent : une entité sur plusieurs lignes
        if re.search(r"(^|_)id(_|$)", name) and 1 < distinct < n_rows:
            line += " <- identifiant répété : utiliser COUNT(DISTINCT) pour compter les entités"
            id_cols.append(name)
        schema_lines.append(line)
    sample = con.execute(f'SELECT * FROM "{table}" LIMIT 3').fetchdf()
    sample_str = sample.to_string(index=False)
    return (
        f"Nom de la table : {table} ({n_rows} lignes)\n\n"
        f"Colonnes :\n" + "\n".join(schema_lines) +
        f"\n\nExemples de lignes :\n{sample_str}"
    )

def text_to_sql(question: str, schema: str, model: str = "qwen2.5-coder:3b") -> dict:
    """Génère une requête SQL à partir d'une question."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{schema}\n\nQuestion : {question}"}
    ]

    try:
        response = ollama.chat(
            model=model,
            messages=messages,
            options={"temperature": 0.1}
        )
        sql = response["message"]["content"].strip()

        # Nettoyage des ```sql
        if "```" in sql:
            parts = sql.split("```")
            sql = parts[1] if len(parts) > 1 else parts[0]
            if sql.lower().startswith("sql"):
                sql = sql[3:]
            sql = sql.strip()

        safe, error = is_safe_sql(sql)
        return {"sql": sql, "safe": safe, "error": error if not safe else None}

    except Exception as e:
        return {"sql": None, "safe": False, "error": str(e)}


def run_sql_with_retry(
    con: duckdb.DuckDBPyConnection,
    question: str,
    table: str = "clean",
    max_retries: int = 3,
    model: str = "qwen2.5-coder:3b"
) -> dict:
    """
    Génère une requête SQL, l'exécute, et corrige automatiquement en cas d'erreur.
    """
    schema = get_schema(con, table)
    history = []

    for attempt in range(1, max_retries + 1):
        result = text_to_sql(question, schema, model=model)
        sql = result["sql"]
        history.append({"attempt": attempt, "sql": sql, "safe": result["safe"]})

        if not result["safe"]:
            history[-1]["error"] = result["error"]
            # On demande au modèle de corriger
            question = f"La requête précédente était invalide : {result['error']}. Corrige-la.\nQuestion originale : {question}"
            continue

        try:
            df = con.execute(sql).fetchdf()
            return {
                "success": True,
                "sql": sql,
                "data": df,
                "attempts": attempt,
                "history": history
            }
        except Exception as e:
            error_msg = str(e)
            history[-1]["error"] = error_msg
            # On renvoie l'erreur DuckDB au modèle pour qu'il corrige
            question = (
                f"La requête SQL suivante a échoué :\n{sql}\n\n"
                f"Erreur DuckDB : {error_msg}\n\n"
                f"Corrige la requête.\nQuestion originale : {question}"
            )

        hint = ""
    if id_cols:
        hint = (f"\n\nExemple : pour compter les entités uniques, utilise "
                f"SELECT COUNT(DISTINCT {id_cols[0]}) FROM {table}")
    return (
        f"Nom de la table : {table} ({n_rows} lignes)\n\n"
        f"Colonnes :\n" + "\n".join(schema_lines) +
        hint +
        f"\n\nExemples de lignes :\n{sample_str}"
    )