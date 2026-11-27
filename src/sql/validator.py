"""Validateur de sécurité SQL : n'autorise que les SELECT simples."""
import sqlglot
from sqlglot import exp


def is_safe_sql(query: str) -> tuple[bool, str]:
    """
    Vérifie qu'une requête SQL est sûre.
    Retourne (True, "") si OK, sinon (False, message d'erreur).
    """
    query = query.strip()
    if not query:
        return False, "Requête vide"

    try:
        # Parse la requête
        parsed = sqlglot.parse(query, read="duckdb")
        if not parsed or len(parsed) != 1:
            return False, "Une seule requête est autorisée"

        statement = parsed[0]

        # Interdit tout ce qui n'est pas un SELECT
        if not isinstance(statement, exp.Select):
            return False, "Seules les requêtes SELECT sont autorisées"

        # Interdit les sous-requêtes dangereuses et les fonctions interdites
        forbidden = {
            exp.Drop, exp.Delete, exp.Update, exp.Insert, exp.Create,
            exp.Alter, exp.Command, exp.Copy, exp.Attach, exp.Detach
        }

        for node in statement.walk():
            if type(node) in forbidden:
                return False, f"Opération interdite détectée : {type(node).__name__}"

        return True, ""

    except Exception as e:
        return False, f"Erreur de parsing SQL : {str(e)}"