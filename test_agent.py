import duckdb
from src.data.loader import load_dataset
from src.agent.agent import Agent

con = duckdb.connect()
load_dataset("data/20260721-irve-driveco.csv", con)
agent = Agent(con)

requests = [
    "Fais un diagnostic des données puis nettoie-les",
    "Montre les 5 stations avec le plus de points de charge sous forme de graphique",
]

for req in requests:
    print("\n" + "=" * 60)
    print("Demande :", req)
    out = agent.run(req)
    print("Plan :", out["steps"], "| Question SQL :", out["question"])
    for e in out["log"]:
        print(f"  [{e['status']}] {e['step']} → {e.get('summary', '')}")
        if "sql" in e:
            print("      SQL :", e["sql"].replace("\n", " "))
        if e.get("fig") is not None:
            e["fig"].write_html("agent_chart.html")
            print("      Graphique sauvegardé → agent_chart.html")
    print("Synthèse :", out["summary"])