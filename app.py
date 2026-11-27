"""Interface Streamlit de l'agent IA d'analyse de données."""
import os
import tempfile

import duckdb
import pandas as pd
import streamlit as st

from src.data.loader import load_dataset
from src.agent.agent import Agent

st.set_page_config(page_title="Agent d'analyse de données", layout="wide")
st.title("Agent IA d'analyse de données")

# ---------- État de session (conservé entre deux interactions) ----------
for key, default in [("history", []), ("agent", None), ("con", None), ("file_key", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------- Barre latérale : import des données ----------
with st.sidebar:
    st.header("1. Données")
    uploaded = st.file_uploader("Importer un fichier CSV ou Excel", type=["csv", "xlsx", "xls"])
    model = st.text_input("Modèle Ollama", value="qwen2.5-coder:3b")
    if st.button("Effacer l'historique"):
        st.session_state.history = []

if uploaded is None:
    st.info("Commence par importer un fichier CSV ou Excel dans la barre latérale.")
    st.stop()

# Charger le fichier seulement s'il est nouveau
file_key = (uploaded.name, uploaded.size)
if st.session_state.file_key != file_key:
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getvalue())
        path = tmp.name
    try:
        con = duckdb.connect()
        load_dataset(path, con)
    except Exception as e:
        st.error(f"Impossible de lire le fichier : {e}")
        st.stop()
    finally:
        os.remove(path)
    st.session_state.con = con
    st.session_state.agent = Agent(con, model)
    st.session_state.file_key = file_key
    st.session_state.history = []

agent = st.session_state.agent
agent.model = model
con = st.session_state.con

n_rows = con.execute("SELECT COUNT(*) FROM raw").fetchone()[0]
with st.expander(f"Aperçu des données ({n_rows} lignes)"):
    st.dataframe(con.execute("SELECT * FROM raw LIMIT 100").fetchdf())

st.caption("Exemples : « Fais un diagnostic puis nettoie les données » · "
           "« Montre les 5 stations avec le plus de points de charge en graphique » · "
           "« Quelle est la puissance moyenne ? »")


# ---------- Affichage d'un résultat de l'agent ----------
def render_result(out: dict, idx: int):
    st.markdown("**Plan :** " + " → ".join(out["steps"]))
    for n, e in enumerate(out["log"]):
        icon = "✅" if e["status"] == "ok" else "❌"
        label = f"{icon} {e['step']} — {e.get('summary', '')[:90]}"
        with st.expander(label, expanded=e["step"] in ("query", "chart")):
            if e["status"] == "error":
                st.error(e.get("summary", "Erreur"))
            elif e["step"] == "diagnose":
                st.dataframe(pd.DataFrame(e["data"]["columns"]))
            elif e["step"] == "clean":
                for line in e.get("details", []):
                    st.write("- " + line)
            elif e["step"] == "query":
                st.code(e["sql"], language="sql")
                st.caption(f"{e['attempts']} tentative(s)")
                st.dataframe(e["data"])
            elif e["step"] == "chart":
                if e.get("fig") is not None:
                    st.plotly_chart(e["fig"], key=f"chart_{idx}_{n}")
                else:
                    st.info(e.get("summary", ""))
    st.markdown("**Synthèse**")
    st.success(out["summary"])


# ---------- Zone de conversation ----------
request = st.chat_input("Que veux-tu faire avec ces données ?")
if request:
    with st.spinner("L'agent travaille..."):
        out = agent.run(request)
    st.session_state.history.append(out)

for i, out in enumerate(st.session_state.history):
    with st.chat_message("user"):
        st.write(out["request"])
    with st.chat_message("assistant"):
        render_result(out, i)
