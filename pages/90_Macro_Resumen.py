# pages/90_Macro_Resumen.py
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import inject_css, range_controls, kpi_quad

st.set_page_config(page_title="Resumen macro – núcleo", layout="wide")
inject_css()
st.title("📈 Resumen macro – núcleo (BCRA + placeholders)")

DATA = "data/macro_core_long.parquet"

@st.cache_data
def load_long():
    if not os.path.exists(DATA):
        return pd.DataFrame()
    df = pd.read_parquet(DATA)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df

df = load_long()
if df.empty:
    st.warning("Aún no existe data/macro_core_long.parquet. Corré el workflow *Build Macro Core (from BCRA)*.")
    st.stop()

indicadores = {
    "reservas_brutas_bcra_usd_bn": "Reservas brutas BCRA",
    "pasivos_remunerados_bcra_usd_bn": "Pasivos remunerados (LELIQ+Pases) – BCRA",
    # cuando estén disponibles: resultado, deuda, inflación núcleo, pobreza, riesgo
}

opts = [df[df["indicador"]==k]["titulo"].iloc[0] for k in indicadores if (df["indicador"]==k).any()]
sel = st.multiselect("Elegí hasta 3 series", options=opts, default=opts[:2], max_selections=3)
if not sel:
    st.info("Seleccioná al menos una serie.")
    st.stop()

# map back to keys
title_to_key = { df[df["indicador"]==k]["titulo"].iloc[0]: k for k in indicadores if (df["indicador"]==k).any() }
keys = [title_to_key[t] for t in sel]

wide = (
    df[df["indicador"].isin(keys)]
    .pivot(index="fecha", columns="titulo", values="valor")
    .sort_index()
)

dmin, dmax = wide.index.min(), wide.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="macro_core", show_government=False)
vis = wide.loc[d_ini:d_fin].dropna(how="all")
if freq_label.startswith("Mensual"):
    vis = vis.resample("M").last()

fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]
for i, name in enumerate(vis.columns):
    s = vis[name].dropna()
    if s.empty:
        continue
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines",
                             name=name, line=dict(width=2, color=palette[i%3]),
                             hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>"))
fig.update_layout(template="atlas_dark", height=620, margin=dict(t=30,b=80,l=70,r=60))
fig.update_xaxes(title_text="Fecha")
fig.update_yaxes(title_text="Valor")

st.plotly_chart(fig, use_container_width=True)

# KPIs (último + MoM + YoY + Δ)
from bcra_utils import resample_series, compute_kpis
palette_cycle = ["#60A5FA", "#F87171", "#34D399"]

for idx, name in enumerate(vis.columns):
    full = wide[name].dropna()
    visible = resample_series(vis[name].dropna(), freq=("D" if freq_label.startswith("Diaria") else "M"), how="last").dropna()
    mom, yoy, d_per = compute_kpis(full, visible)
    last_val = visible.iloc[-1] if not visible.empty else None
    kpi_quad(
        title=name,
        color=palette_cycle[idx%len(palette_cycle)],
        last_value=last_val,
        is_percent=False,
        mom=mom, yoy=yoy, d_per=d_per,
        tip_last="Último dato del rango visible.",
        tip_mom="Δ vs mes anterior (último dato mensual).",
        tip_yoy="Δ vs mismo mes del año previo.",
        tip_per="Δ entre el primero y el último del período visible.",
    )
