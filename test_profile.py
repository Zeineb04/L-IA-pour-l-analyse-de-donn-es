import duckdb
from src.data.loader import load_dataset
from src.data.profiler import profile_table

con = duckdb.connect()
load_dataset("data/20260721-irve-driveco.csv", con)   # mettez votre vrai nom de fichier
p = profile_table(con)
print(p["rows"], "lignes,", p["columns"], "colonnes,", p["duplicates"], "doublons")
for issue in p["issues"]:
    print("-", issue)