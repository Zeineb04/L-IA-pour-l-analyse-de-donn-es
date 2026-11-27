import duckdb
from src.data.loader import load_dataset
from src.data.cleaner import clean_table
from src.sql.text_to_sql import run_sql_with_retry

con = duckdb.connect()
load_dataset("data/20260721-irve-driveco.csv", con)
clean_table(con, drop_constant=True)

questions = [
    "Combien de points de charge y a-t-il au total ?",
    "Combien de stations y a-t-il ?",
    "Montre les 5 stations avec le plus de points de charge",
]

for q in questions:
    print("\n" + "=" * 60)
    print("Question :", q)
    r = run_sql_with_retry(con, q)
    if r["success"]:
        print("SQL :", r["sql"])
        print(r["data"].to_string(index=False))
    else:
        print("Échec")
        