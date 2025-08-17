# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

st.set_page_config(page_title="Macro Argentina – BCRA", layout="wide")
st.title("🇦🇷 Macro Argentina – BCRA (API v3, auto-actualizado)")

CSV_LONG = Path("data/monetarias_long.csv")
CAT_JSON  = Path("data/monetarias_catalogo.json")

# -------------------- loaders con cache --------------------
@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(CSV_LONG)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["fecha"]).sort_values(["descripcion", "fecha"])
    return df

@st.cache_data(ttl=3600)
def load_catalog():
    cat = pd.read_json(CAT_JSON)
    cat["descripcion"] = cat["descripcion"].astype(str).str.strip()
    return cat

df = load_data()
cat = load_catalog()

# Variables disponibles (con datos válidos)
vars_con_datos = sorted(df["descripcion"].dropna().unique().tolist())
if not vars_con_datos:
    st.error("No hay variables con datos válidos. Verificá data/monetarias_long.csv")
    st.stop()

# -------------------- Sidebar --------------------
st.sidebar.header("Parámetros")
default_1 = next((v for v in vars_con_datos if "base monetaria" in v.lower()), vars_con_datos[0])

seleccion = st.sidebar.multiselect(
    "Seleccioná 1 o 2 variables",
    options=vars_con_datos,
    default=[default_1],
    max_selections=2,
)

if not seleccion:
    st.info("Elegí al menos una variable para graficar.")
    st.stop()

# Dataset filtrado
df_sel = df[df["descripcion"].isin(seleccion)].copy()
df_sel["fecha"] = pd.to_datetime(df_sel["fecha"], errors="coerce")
df_sel = df_sel.dropna(subset=["fecha"]).sort_values(["descripcion", "fecha"])
if df_sel.empty:
    st.warning("No hay datos con fechas válidas para la selección.")
    st.stop()

# Rango de fechas sugerido por los datos presentes
fmin = df_sel["fecha"].min().date()
fmax = df_sel["fecha"].max().date()

c1, c2 = st.columns(2)
with c1:
    d_ini = st.date_input("Desde", value=fmin, min_value=fmin, max_value=fmax)
with c2:
    d_fin = st.date_input("Hasta", value=fmax, min_value=fmin, max_value=fmax)

if pd.to_datetime(d_ini) > pd.to_datetime(d_fin):
    d_ini, d_fin = d_fin, d_ini

mask = (df_sel["fecha"] >= pd.to_datetime(d_ini)) & (df_sel["fecha"] <= pd.to_datetime(d_fin))
df_sel = df_sel.loc[mask]
if df_sel.empty:
    st.info("No hay observaciones en el rango elegido.")
    st.stop()

# -------------------- Gráficos --------------------
legend_bottom = dict(
    orientation="h",
    yanchor="bottom",
    y=-0.3,          # debajo del chart
    xanchor="center",
    x=0.5
)
margins = dict(t=50, b=100)

if len(seleccion) == 1:
    titulo = seleccion[0]
    serie = df_sel[df_sel["descripcion"] == seleccion[0]]
    fig = px.line(
        serie,
        x="fecha",
        y="valor",
        title=titulo,
        labels={"fecha": "Fecha", "valor": "Valor"},
    )
    fig.update_layout(legend=legend_bottom, margin=margins)
    st.plotly_chart(fig, use_container_width=True)

    last = serie.iloc[-1]
    st.metric("Último dato visible", f"{last['valor']:,.0f}", help=f"Fecha: {last['fecha'].date()}")

else:
    var1, var2 = seleccion
    st.subheader(f"Comparación: {var1} vs {var2}")

    modo = st.radio(
        "Modo de comparación",
        ["Mismo eje", "Doble eje Y", "Base 100 (desde el primer dato del rango)"],
        index=1,
        horizontal=False,
    )

    wide = df_sel.pivot_table(index="fecha", columns="descripcion", values="valor", aggfunc="last").sort_index()
    s1 = wide[var1].dropna()
    s2 = wide[var2].dropna()

    if s1.empty or s2.empty:
        st.warning("Alguna de las variables no tiene datos en el rango seleccionado.")
        st.stop()

    if modo == "Mismo eje":
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s1.index, y=s1.values, name=var1, mode="lines"))
        fig.add_trace(go.Scatter(x=s2.index, y=s2.values, name=var2, mode="lines"))
        fig.update_layout(
            title=f"{var1} y {var2} (mismo eje)",
            xaxis_title="Fecha",
            yaxis_title="Valor",
            legend=legend_bottom,
            margin=margins,
        )

    elif modo == "Doble eje Y":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=s1.index, y=s1.values, name=var1, mode="lines"), secondary_y=False)
        fig.add_trace(go.Scatter(x=s2.index, y=s2.values, name=var2, mode="lines"), secondary_y=True)
        fig.update_xaxes(title_text="Fecha")
        fig.update_yaxes(title_text=var1, secondary_y=False)
        fig.update_yaxes(title_text=var2, secondary_y=True)
        fig.update_layout(
            title=f"{var1} vs {var2} (doble eje Y)",
            legend=legend_bottom,
            margin=margins,
        )

    else:  # Base 100
        b1 = s1.iloc[0]
        b2 = s2.iloc[0]
        s1_norm = (s1 / b1) * 100
        s2_norm = (s2 / b2) * 100
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s1_norm.index, y=s1_norm.values, name=f"{var1} (Base=100)"))
        fig.add_trace(go.Scatter(x=s2_norm.index, y=s2_norm.values, name=f"{var2} (Base=100)"))
        fig.update_layout(
            title=f"{var1} vs {var2} (Base 100)",
            xaxis_title="Fecha",
            yaxis_title="Índice (Base 100)",
            legend=legend_bottom,
            margin=margins,
        )

    st.plotly_chart(fig, use_container_width=True)

    # Métricas
    c1, c2 = st.columns(2)
    last1 = s1.dropna().iloc[-1]
    last2 = s2.dropna().iloc[-1]
    with c1:
        st.metric(f"Último {var1}", f"{last1:,.0f}", help=f"Fecha: {s1.dropna().index[-1].date()}")
    with c2:
        st.metric(f"Último {var2}", f"{last2:,.0f}", help=f"Fecha: {s2.dropna().index[-1].date()}")

# -------------------- Descarga --------------------
with st.expander("Descargar CSV (rango filtrado y selección)"):
    st.download_button(
        "Descargar",
        data=df_sel.to_csv(index=False).encode("utf-8"),
        file_name="seleccion_filtrada.csv",
        mime="text/csv",
    )
