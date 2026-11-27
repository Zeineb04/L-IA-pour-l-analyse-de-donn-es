import duckdb
from src.data.loader import load_dataset
from src.data.cleaner import clean_table
from src.sql.text_to_sql import run_sql_with_retry
from src.viz.charts import make_chart

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
        print("SQL :", result["sql"])
        chart = make_chart(result["data"], question=q)
        print("Type de graphique :", chart["type"])
        print("Message :", chart["message"])

        # Sauvegarde le graphique pour vérification
        if chart["fig"] is not None:
            filename = f"chart_{questions.index(q)+1}.html"
            chart["fig"].write_html(filename)
            print(f"Graphique sauvegardé → {filename}")
    else:
        print("Échec de la requête")