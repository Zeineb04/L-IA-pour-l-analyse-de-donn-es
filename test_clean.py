import duckdb
from src.data.loader import load_dataset
from src.data.cleaner import clean_table

con = duckdb.connect()
load_dataset("data/20260721-irve-driveco.csv", con)
r = clean_table(con, drop_constant=True, outliers=None)
print(r["rows_before"], "->", r["rows_after"], "lignes |", r["cols_before"], "->", r["cols_after"], "colonnes")
for line in r["log"]:
    print("-", line)