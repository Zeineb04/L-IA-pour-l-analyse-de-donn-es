"""Génération de SQL + exécution + auto-correction via Ollama."""
import ollama
import duckdb
from src.sql.validator import is_safe_sql


SYSTEM_PROMPT = """Tu es un expert SQL pour DuckDB.
Tu dois répondre UNIQUEMENT avec une requête SQL SELECT valide.
N'écris aucun texte avant ou après la requête.
N'utilise jamais DROP, DELETE, UPDATE, INSERT, CREATE, ALTER, COPY, ATTACH.
Utilise UNIQUEMENT le nom de table et les colonnes fournis.
"""


def get_schema(con, table: str = "clean") -> str:
    """Retourne le schéma + 3 lignes d'exemple."""
    cols = con.execute(f'DESCRIBE "{table}"').fetchall()
    schema_lines = [f"- {c[0]} ({c[1]})" for c in cols]
    sample = con.execute(f'SELECT * FROM "{table}" LIMIT 3').fetchdf()
    sample_str = sample.to_string(index=False)
    return (
        f"Nom de la table : {table}\n\n"
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

    return {
        "success": False,
        "sql": None,
        "data": None,
        "attempts": max_retries,
        "history": history,
        "error": "Échec après plusieurs tentatives"
    }