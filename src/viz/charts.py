"""Génération automatique de graphiques Plotly à partir d'un DataFrame."""
import pandas as pd
import plotly.express as px

MAX_CATEGORIES = 20


def _column_kinds(df: pd.DataFrame):
    """Classe les colonnes : numériques, dates, et tout le reste = catégories."""
    numeric = df.select_dtypes(include="number").columns.tolist()
    dates = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
    categorical = [c for c in df.columns if c not in numeric and c not in dates]
    return numeric, categorical, dates


def make_chart(df: pd.DataFrame, question: str = "") -> dict:
    """Choisit et génère un graphique adapté au DataFrame."""
    if df is None or df.empty:
        return {"fig": None, "type": None, "message": "Aucune donnée à afficher"}

    # Une seule valeur (agrégation) : pas de graphique
    if len(df) == 1 and len(df.columns) <= 2:
        return {"fig": None, "type": "metric",
                "message": f"Résultat : {df.iloc[0].to_dict()}"}

    numeric, categorical, dates = _column_kinds(df)
    title = question or "Résultat"

    if dates and numeric:                      # date + nombre -> courbe
        fig = px.line(df.sort_values(dates[0]), x=dates[0], y=numeric[0], title=title)
        chart_type = "line"
    elif categorical and numeric:              # catégorie + nombre -> barres
        cat, num = categorical[0], numeric[0]
        data = df.sort_values(num, ascending=False).head(MAX_CATEGORIES)
        color = categorical[1] if len(categorical) > 1 else None
        fig = px.bar(data, x=cat, y=num, color=color, title=title)
        chart_type = "bar"
    elif len(numeric) >= 2:                    # deux nombres -> nuage de points
        fig = px.scatter(df, x=numeric[0], y=numeric[1], title=title)
        chart_type = "scatter"
    else:
        return {"fig": None, "type": "table",
                "message": "Données affichées sous forme de tableau"}

    fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
    return {"fig": fig, "type": chart_type, "message": f"Graphique de type {chart_type} généré"}