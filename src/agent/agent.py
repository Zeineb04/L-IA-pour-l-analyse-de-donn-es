"""Agent IA : planification + enchaînement des outils + synthèse."""
import json
import ollama

from src.data.diagnostic import diagnose
from src.data.cleaner import clean_table
from src.sql.text_to_sql import run_sql_with_retry
from src.viz.charts import make_chart

MODEL = "qwen2.5-coder:3b"
ORDER = ["diagnose", "clean", "query", "chart"]  # ordre logique des outils

PLANNER_PROMPT = """Tu es le planificateur d'un agent d'analyse de données.
Outils disponibles :
- diagnose : diagnostic de qualité des données (valeurs manquantes, doublons, types)
- clean : nettoyage des données
- query : répondre à une question sur les données avec une requête SQL
- chart : afficher un graphique du résultat d'une requête

Réponds UNIQUEMENT avec du JSON de la forme :
{"steps": ["..."], "question": "..."}
"steps" contient uniquement des noms d'outils. "question" est la partie de la
demande qui porte sur les données (chaîne vide s'il n'y a pas de question).

Exemples :
Demande : Nettoie les données
{"steps": ["clean"], "question": ""}
Demande : Fais un diagnostic puis montre les 5 stations avec le plus de bornes en graphique
{"steps": ["diagnose", "query", "chart"], "question": "Les 5 stations avec le plus de bornes"}
Demande : Quelle est la puissance moyenne ?
{"steps": ["query"], "question": "Quelle est la puissance moyenne ?"}
"""


def fallback_plan(request: str) -> tuple[list, str]:
    """Plan par mots-clés si le modèle ne renvoie pas un JSON exploitable."""
    r = request.lower()
    steps = []
    if any(k in r for k in ("diagnos", "qualité", "qualite", "manquant", "analyse")):
        steps.append("diagnose")
    if any(k in r for k in ("nettoi", "clean", "doublon")):
        steps.append("clean")
    if any(k in r for k in ("graph", "montre", "visualis", "courbe", "histogramme", "barres")):
        steps.append("chart")
    if any(k in r for k in ("combien", "quel", "quelle", "moyenne", "total", "top", "montre", "liste")):
        steps.append("query")
    if not steps:
        steps = ["query"]
    return steps, request


def fix_plan(steps: list) -> list:
    """Garde les outils valides, sans doublons, dans l'ordre logique."""
    steps = {s for s in steps if s in ORDER}
    if "chart" in steps:
        steps.add("query")  # un graphique a besoin d'un résultat de requête
    return [s for s in ORDER if s in steps]


def plan(request: str, model: str = MODEL) -> tuple[list, str]:
    try:
        resp = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": PLANNER_PROMPT},
                {"role": "user", "content": f"Demande : {request}"},
            ],
            format="json",
            options={"temperature": 0},
        )
        data = json.loads(resp["message"]["content"])
        steps = fix_plan(data.get("steps", []))
        question = (data.get("question") or "").strip() or request
        if steps:
            return steps, question
    except Exception:
        pass
    steps, question = fallback_plan(request)
    return fix_plan(steps), question


class Agent:
    def __init__(self, con, model: str = MODEL):
        self.con = con
        self.model = model
        self.last_df = None

    def _table(self) -> str:
        tables = [t[0] for t in self.con.execute("SHOW TABLES").fetchall()]
        return "clean" if "clean" in tables else "raw"

    # ----- outils -----
    def _do_diagnose(self, question: str) -> dict:
        d = diagnose(self.con, self._table())
        with_nulls = [f"{c['name']} ({c['null_pct']}%)"
                      for c in d["columns"] if c["null_pct"] > 0]
        summary = (f"{d['rows']} lignes, {d['cols']} colonnes, {d['duplicates']} doublons. "
                   f"Colonnes avec valeurs manquantes : "
                   + (", ".join(with_nulls) if with_nulls else "aucune"))
        return {"summary": summary, "data": d}

    def _do_clean(self, question: str) -> dict:
        r = clean_table(self.con, drop_constant=True)
        summary = (f"Lignes {r['rows_before']} → {r['rows_after']}, "
                   f"colonnes {r['cols_before']} → {r['cols_after']}. "
                   + " ; ".join(r["log"]))
        return {"summary": summary, "details": r["log"]}

    def _do_query(self, question: str) -> dict:
        r = run_sql_with_retry(self.con, question, table=self._table(), model=self.model)
        if not r["success"]:
            raise RuntimeError(f"Échec SQL après {r['attempts']} tentatives")
        self.last_df = r["data"]
        return {"summary": f"{len(r['data'])} ligne(s), {r['attempts']} tentative(s)",
                "sql": r["sql"], "attempts": r["attempts"], "data": r["data"]}

    def _do_chart(self, question: str) -> dict:
        if self.last_df is None:
            raise RuntimeError("Aucun résultat à représenter")
        c = make_chart(self.last_df, question)
        return {"summary": c["message"], "fig": c["fig"], "chart_type": c["type"]}

    # ----- synthèse -----
    def _summarize(self, request: str, log: list) -> str:
        lines = [f"- {e['step']} : {e['status']} - {e.get('summary', '')}" for e in log]
        text = "\n".join(lines)
        if self.last_df is not None:
            text += "\n\nDonnées obtenues :\n" + self.last_df.head(10).to_string(index=False)
        try:
            resp = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Tu es un analyste de données. Écris en français une synthèse de 2 à 4 phrases, claire. "
                            "Utilise uniquement les informations fournies : n'invente ni chiffres ni explications "
                            "qui ne figurent pas dans les opérations."},
                    {"role": "user", "content": f"Demande : {request}\n\nOpérations effectuées :\n{text}"},
                ],
                options={"temperature": 0.2},
            )
            return resp["message"]["content"].strip()
        except Exception as e:
            return f"(Synthèse indisponible : {e})"

    # ----- boucle principale -----
    def run(self, request: str) -> dict:
        steps, question = plan(request, self.model)
        log = []
        for step in steps:
            entry = {"step": step}
            try:
                entry.update(getattr(self, f"_do_{step}")(question))
                entry["status"] = "ok"
            except Exception as e:
                entry["status"] = "error"
                entry["summary"] = str(e)
            log.append(entry)
            if entry["status"] == "error" and step == "query":
                break  # inutile de tracer un graphique sans résultat
        return {"request": request, "steps": steps, "question": question,
                "log": log, "summary": self._summarize(request, log)}