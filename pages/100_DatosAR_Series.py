# pages/100_DatosAR_Series.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from ui import inject_css, range_controls, kpi_quad, clean_label, looks_percent

st.set_page_config(page_title="Series de Datos Argentina", layout="wide")
inject_css()
st.title("🇦🇷 Series de Datos Argentina")

LONG = "data/datosar_long.parquet"
CAT  = "data/datosar_catalog_meta.parquet"

@st.cache_data
def load_long():
    try:
        df = pd.read_parquet(LONG)
        df["fecha"] = pd.to_datetime(df["fecha"])
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data
def load_catalog():
    try:
        return pd.read_parquet(CAT)
    except Exception:
        return pd.DataFrame()

df = load_long()
cat = load_catalog()

if df.empty or cat.empty:
    st.warning("Todavía no hay datos locales de DatosAR. Corré el fetch de catálogo + datos.")
    st.stop()

# sidebar de grupo
grupos = ["(todos)"] + sorted(cat["group"].unique().tolist())
g_sel = st.selectbox("Grupo", grupos, index=0)
if g_sel != "(todos)":
    options = sorted(cat[cat["group"]==g_sel]["name"].unique().tolist())
else:
    options = sorted(cat["name"].unique().tolist())

sel = st.multiselect("Elegí hasta 3 series", options=options, max_selections=3)
if not sel:
    st.info("Seleccioná al menos una serie.")
    st.stop()

wide = (
    df[df["descripcion"].isin(sel)]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

dmin, dmax = wide.index.min(), wide.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="datosar", show_government=False)
freq = "D" if freq_label.startswith("Diaria") else "M"

vis = wide.loc[d_ini:d_fin]
if freq == "M":
    vis = vis.resample("M").last()
vis = vis.dropna(how="all")

fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

for i, name in enumerate(sel):
    s = vis[name].dropna()
    if s.empty:
        continue
    color = palette[i % len(palette)]
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=clean_label(name),
            line=dict(width=2, color=color),
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

fig.update_layout(
    template="atlas_dark", height=620,
    margin=dict(t=30, b=80, l=70, r=60),
    showlegend=True
)
fig.update_xaxes(title_text="Fecha")
fig.update_yaxes(title_text="Valor")

st.plotly_chart(fig, use_container_width=True)

# KPIs (cuádruple: último + MoM + YoY + Δ)
from bcra_utils import resample_series, compute_kpis  # reutilizamos helpers

def kpis_for(name: str, color: str):
    full = (
        df[df["descripcion"] == name]
        .set_index("fecha")["valor"]
        .sort_index()
        .astype(float)
    )
    visible = resample_series(
        vis[name].dropna(),
        freq=("D" if freq_label.startswith("Diaria") else "M"),
        how="last",
    ).dropna()

    mom, yoy, d_per = compute_kpis(full, visible)
    last_val = visible.iloc[-1] if not visible.empty else None
    kpi_quad(
        title=name,
        color=color,
        last_value=last_val,
        is_percent=looks_percent(name),
        mom=mom, yoy=yoy, d_per=d_per,
        tip_last="Último dato del rango visible (con frecuencia elegida).",
        tip_mom="Variación del último dato mensual vs el mes previo.",
        tip_yoy="Variación vs mismo mes del año previo.",
        tip_per="Variación entre primer y último dato del período visible.",
    )

for idx, name in enumerate(sel):
    kpis_for(name, palette[idx % len(palette)])
