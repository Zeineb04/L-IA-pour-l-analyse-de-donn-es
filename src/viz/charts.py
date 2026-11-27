"""Génération automatique de graphiques Plotly à partir d'un DataFrame."""
import plotly.express as px
import pandas as pd


def make_chart(df: pd.DataFrame, question: str = "") -> dict:
    """
    Choisit et génère un graphique adapté au DataFrame.
    Retourne un dict avec la figure Plotly et une explication.
    """
    if df is None or df.empty:
        return {"fig": None, "type": None, "message": "Aucune donnée à afficher"}

    cols = list(df.columns)
    n_rows = len(df)

    # Cas 1 : une seule valeur (agrégation)
    if n_rows == 1 and len(cols) <= 2:
        return {
            "fig": None,
            "type": "metric",
            "message": f"Résultat : {df.iloc[0].to_dict()}"
        }

    # Détection des types de colonnes
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "bool", "category"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()

    fig = None
    chart_type = None

    # Cas 2 : 2 colonnes → un graphique simple
    if len(cols) == 2:
        col1, col2 = cols[0], cols[1]

        if col1 in categorical_cols and col2 in numeric_cols:
            # Catégorie + nombre → barres
            fig = px.bar(df, x=col1, y=col2, title=question or f"{col2} par {col1}")
            chart_type = "bar"

        elif col1 in numeric_cols and col2 in categorical_cols:
            fig = px.bar(df, x=col2, y=col1, title=question or f"{col1} par {col2}")
            chart_type = "bar"

        elif col1 in datetime_cols and col2 in numeric_cols:
            fig = px.line(df, x=col1, y=col2, title=question or f"{col2} au fil du temps")
            chart_type = "line"

        elif col1 in numeric_cols and col2 in numeric_cols:
            fig = px.scatter(df, x=col1, y=col2, title=question or f"{col2} vs {col1}")
            chart_type = "scatter"

        else:
            # Fallback : barres
            fig = px.bar(df, x=col1, y=col2, title=question or "Graphique")
            chart_type = "bar"

    # Cas 3 : plus de 2 colonnes → on prend les 2 premières pertinentes
    elif len(numeric_cols) >= 1 and len(categorical_cols) >= 1:
        cat = categorical_cols[0]
        num = numeric_cols[0]
        fig = px.bar(df, x=cat, y=num, title=question or f"{num} par {cat}")
        chart_type = "bar"

    elif len(numeric_cols) >= 2:
        fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1],
                         title=question or f"{numeric_cols[1]} vs {numeric_cols[0]}")
        chart_type = "scatter"

    else:
        # Dernier recours : table
        return {
            "fig": None,
            "type": "table",
            "message": "Données affichées sous forme de tableau"
        }

    if fig:
        fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))

    return {
        "fig": fig,
        "type": chart_type,
        "message": f"Graphique de type {chart_type} généré"
    }