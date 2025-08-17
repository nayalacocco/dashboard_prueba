# streamlit_app.py (ajustado)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import textwrap

st.set_page_config(page_title="Macro Argentina – BCRA", layout="wide")
st.title("🇦🇷 Macro Argentina – BCRA (API v3, auto-actualizado)")

CSV_LONG = Path("data/monetarias_long.csv")
CAT_JSON  = Path("data/monetarias_catalogo.json")

@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(CSV_LONG)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["fecha"]).sort_values(["descripcion", "fecha"])

@st.cache_data(ttl=3600)
def load_catalog():
    return pd.read_json(CAT_JSON)

df = load_data()
cat = load_catalog()

# ---------------- Sidebar ----------------
st.sidebar.header("Parámetros")
vars_con_datos = sorted(df["descripcion"].dropna().unique().tolist())
default = next((v for v in vars_con_datos if "base monetaria" in v.lower()), vars_con_datos[0])

seleccion = st.sidebar.multiselect(
    "Seleccioná 1 o 2 variables",
    options=vars_con_datos,
    default=[default],
    max_selections=2,
)

if not seleccion:
    st.stop()

df_sel = df[df["descripcion"].isin(seleccion)]
fmin, fmax = df_sel["fecha"].min().date(), df_sel["fecha"].max().date()

c1, c2 = st.columns(2)
with c1:
    d_ini = st.date_input("Desde", value=fmin, min_value=fmin, max_value=fmax)
with c2:
    d_fin = st.date_input("Hasta", value=fmax, min_value=fmin, max_value=fmax)

mask = (df_sel["fecha"] >= pd.to_datetime(d_ini)) & (df_sel["fecha"] <= pd.to_datetime(d_fin))
df_sel = df_sel.loc[mask]

if df_sel.empty:
    st.warning("No hay datos en el rango elegido.")
    st.stop()

# ---------------- Legend helper ----------------
def wrap_label(label, width=40):
    return "<br>".join(textwrap.wrap(label, width))

legend_bottom = dict(
    orientation="h",
    yanchor="bottom",
    y=-0.35,
    xanchor="center",
    x=0.5,
)

# ---------------- Plot ----------------
if len(seleccion) == 1:
    var = seleccion[0]
    serie = df_sel[df_sel["descripcion"] == var]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=serie["fecha"], y=serie["valor"], name=wrap_label(var), mode="lines"))
    fig.update_layout(
        title=wrap_label(var, 60),
        xaxis_title="Fecha",
        yaxis_title="Valor",
        legend=legend_bottom,
        margin=dict(t=50, b=120),
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    var1, var2 = seleccion
    modo = st.radio("Modo de comparación", ["Mismo eje", "Doble eje Y", "Base 100"], index=1)

    wide = df_sel.pivot(index="fecha", columns="descripcion", values="valor")

    s1, s2 = wide[var1].dropna(), wide[var2].dropna()

    if modo == "Mismo eje":
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s1.index, y=s1, name=wrap_label(var1), mode="lines"))
        fig.add_trace(go.Scatter(x=s2.index, y=s2, name=wrap_label(var2), mode="lines"))
        fig.update_layout(
            title=wrap_label(f"{var1} vs {var2}", 60),
            xaxis_title="Fecha",
            yaxis_title="Valor",
            legend=legend_bottom,
            margin=dict(t=50, b=120),
        )

    elif modo == "Doble eje Y":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=s1.index, y=s1, name=wrap_label(var1), mode="lines"), secondary_y=False)
        fig.add_trace(go.Scatter(x=s2.index, y=s2, name=wrap_label(var2), mode="lines"), secondary_y=True)
        fig.update_xaxes(title="Fecha")
        # Etiquetas compactas en los ejes, nombres completos en la leyenda
        fig.update_yaxes(title_text="Eje Izq", secondary_y=False)
        fig.update_yaxes(title_text="Eje Der", secondary_y=True)
        fig.update_layout(
            title=wrap_label(f"{var1} vs {var2} (doble eje Y)", 60),
            legend=legend_bottom,
            margin=dict(t=50, b=120),
        )

    else:  # Base 100
        base1, base2 = s1.iloc[0], s2.iloc[0]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s1.index, y=(s1/base1)*100, name=wrap_label(var1), mode="lines"))
        fig.add_trace(go.Scatter(x=s2.index, y=(s2/base2)*100, name=wrap_label(var2), mode="lines"))
        fig.update_layout(
            title=wrap_label(f"{var1} vs {var2} (Base 100)", 60),
            xaxis_title="Fecha",
            yaxis_title="Índice (Base 100)",
            legend=legend_bottom,
            margin=dict(t=50, b=120),
        )

    st.plotly_chart(fig, use_container_width=True)
