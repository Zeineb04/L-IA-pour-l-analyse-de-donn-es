import duckdb
from src.data.loader import load_dataset
from src.data.cleaner import clean_table
from src.sql.text_to_sql import run_sql_with_retry

con = duckdb.connect()
load_dataset("data/20260721-irve-driveco.csv", con)
clean_table(con, drop_constant=True)

questions = [
    "Combien de bornes y a-t-il au total ?",
    "Quelle est la puissance moyenne des bornes ?",
    "Montre les 5 stations avec le plus de points de charge"
]

for q in questions:
    print("\n" + "="*60)
    print("Question :", q)
    result = run_sql_with_retry(con, q)

    if result["success"]:
        print(f"Succès en {result['attempts']} tentative(s)")
        print("SQL :", result["sql"])
        print(result["data"].head())
    else:
        print("Échec")
        print("Historique :")
        for h in result["history"]:
            print(f"  Tentative {h['attempt']} → {h.get('sql')}")
            if "error" in h:
                print(f"    Erreur : {h['error']}")