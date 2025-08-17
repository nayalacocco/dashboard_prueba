import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import textwrap

DATA_DIR = Path("data")
CATALOGO_PATH = DATA_DIR / "catalogo_monetarias.csv"

st.set_page_config(
    page_title="Macro Argentina – BCRA",
    layout="wide",
    page_icon="🇦🇷"
)

st.title("🇦🇷 Macro Argentina – BCRA (API v3, auto-actualizado)")

# cargar catálogo
if not CATALOGO_PATH.exists():
    st.error("No encontré catálogo. Corré el fetch primero.")
    st.stop()

cat = pd.read_csv(CATALOGO_PATH)

# selector de variables
vars_opts = cat["descripcion"].tolist()
vars_sel = st.sidebar.multiselect(
    "Seleccioná 1 o 2 variables",
    vars_opts,
    default=vars_opts[:1],
    max_selections=2
)

if not vars_sel:
    st.warning("Seleccioná al menos una variable.")
    st.stop()

# cargar dataframes de variables seleccionadas
dfs = {}
for var in vars_sel:
    f = DATA_DIR / f"{var}.csv"
    if not f.exists():
        st.error(f"No encontré archivo para {var}")
        st.stop()
    df = pd.read_csv(f, parse_dates=["fecha"])
    dfs[var] = df

# definir rango de fechas
min_date = min(df["fecha"].min() for df in dfs.values())
max_date = max(df["fecha"].max() for df in dfs.values())

c1, c2 = st.columns(2)
d_ini = c1.date_input("Desde", min_date.date(), min_value=min_date.date(), max_value=max_date.date())
d_fin = c2.date_input("Hasta", max_date.date(), min_value=min_date.date(), max_value=max_date.date())

# filtrar datos
dfs = {
    var: df[(df["fecha"] >= pd.to_datetime(d_ini)) & (df["fecha"] <= pd.to_datetime(d_fin))]
    for var, df in dfs.items()
}

# modo de comparación
modo = st.radio("Modo de comparación", ["Mismo eje", "Doble eje Y", "Base 100"], horizontal=True)

# preparar figura
fig = go.Figure()

legend_bottom = dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5)
margins = dict(l=50, r=50, t=50, b=80)

def wrap_label(label, width=40):
    return "<br>".join(textwrap.wrap(label, width=width))

if len(dfs) == 1:
    # una sola variable
    var = vars_sel[0]
    df = dfs[var]
    fig.add_trace(go.Scatter(x=df["fecha"], y=df["valor"], mode="lines", name=var))
    fig.update_layout(
        title=wrap_label(var, 60),
        xaxis_title="Fecha",
        yaxis_title="Valor",
        legend=legend_bottom,
        margin=margins,
        height=650
    )
else:
    # dos variables
    var1, var2 = vars_sel
    df1, df2 = dfs[var1], dfs[var2]

    if modo == "Mismo eje":
        fig.add_trace(go.Scatter(x=df1["fecha"], y=df1["valor"], mode="lines", name=var1))
        fig.add_trace(go.Scatter(x=df2["fecha"], y=df2["valor"], mode="lines", name=var2))
        fig.update_layout(
            title=wrap_label(f"{var1} y {var2} (mismo eje)", 60),
            xaxis_title="Fecha",
            yaxis_title="Valor",
            legend=legend_bottom,
            margin=margins,
            height=650
        )

    elif modo == "Doble eje Y":
        fig.add_trace(go.Scatter(x=df1["fecha"], y=df1["valor"], mode="lines", name=var1, yaxis="y1"))
        fig.add_trace(go.Scatter(x=df2["fecha"], y=df2["valor"], mode="lines", name=var2, yaxis="y2"))
        fig.update_layout(
            title=wrap_label(f"{var1} vs {var2} (doble eje Y)", 60),
            xaxis=dict(domain=[0, 1]),
            yaxis=dict(title="Eje izq", position=0),
            yaxis2=dict(title="Eje der", overlaying="y", side="right"),
            legend=legend_bottom,
            margin=margins,
            height=650
        )

    elif modo == "Base 100":
        base1 = df1["valor"].iloc[0]
        base2 = df2["valor"].iloc[0]
        fig.add_trace(go.Scatter(x=df1["fecha"], y=df1["valor"] / base1 * 100, mode="lines", name=f"{var1} (base 100)"))
        fig.add_trace(go.Scatter(x=df2["fecha"], y=df2["valor"] / base2 * 100, mode="lines", name=f"{var2} (base 100)"))
        fig.update_layout(
            title=wrap_label(f"{var1} vs {var2} (base 100)", 60),
            xaxis_title="Fecha",
            yaxis_title="Índice (base 100)",
            legend=legend_bottom,
            margin=margins,
            height=650
        )

# mostrar grafico
st.plotly_chart(fig, use_container_width=True)

# descargar CSV
if st.checkbox("📥 Descargar CSV (rango filtrado y selección)"):
    out = pd.concat(dfs.values(), axis=0)
    csv = out.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar CSV", csv, file_name="bcra_variables.csv", mime="text/csv")
