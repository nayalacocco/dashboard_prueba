# pages/100_DatosAR_Series.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from ui import inject_css, series_picker, range_controls, clean_label, kpi
from datosar_utils import load_datosar_meta, load_datosar_long

st.set_page_config(page_title="Series de Datos Argentina", layout="wide")
inject_css()
st.title("🇦🇷 Series de Datos Argentina")

st.caption("Catálogo local construido desde la API de Datos Argentina (Series-Tiempo-AR). "
           "El fetch nocturno usa `data/datosar_allowlist.txt` o `data/datosar_keywords.txt`.")

meta = load_datosar_meta()
long = load_datosar_long()
if not meta or long.empty:
    st.warning("Todavía no hay datos locales. Corré el fetch `scripts/fetch_datosar.py`.")
    st.stop()

# Map id -> title
id2title = {m["id"]: m.get("title") or m["id"] for m in meta}
titles_sorted = [clean_label(id2title[i]) for i in id2title]
id_by_clean = {clean_label(id2title[i]): i for i in id2title}

# Picker (hasta 3)
sel_clean = series_picker(
    titles_sorted,
    default=titles_sorted[:3],
    key="datosar",
    title="Elegí hasta 3 series",
    subtitle="Podés combinar libremente (usamos eje doble si las magnitudes difieren mucho).",
)
if not sel_clean:
    st.info("Elegí al menos una serie.")
    st.stop()

sel_ids = [id_by_clean[c] for c in sel_clean]

# Wide
wide = (long[long["id"].isin(sel_ids)]
        .pivot(index="fecha", columns="id", values="valor")
        .sort_index()
        .dropna(how="all"))

dmin, dmax = wide.index.min().date(), wide.index.max().date()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="datosar")
wide_vis = wide.loc[str(d_ini):str(d_fin)]
if freq_label.startswith("Mensual"):
    wide_vis = wide_vis.resample("M").last()

# Fig
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]
for i, sid in enumerate(sel_ids):
    s = wide_vis[sid].dropna()
    if s.empty: continue
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=clean_label(id2title.get(sid, sid)),
        line=dict(width=2, color=palette[i % len(palette)]),
        hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))
fig.update_layout(template="atlas_dark", height=600, margin=dict(t=30,b=60,l=70,r=70), showlegend=True)
fig.update_xaxes(title_text="Fecha")
fig.update_yaxes(title_text="Valor")
st.plotly_chart(fig, use_container_width=True)

# KPIs últimos valores
st.subheader("Últimos valores")
for i, sid in enumerate(sel_ids):
    s_full = wide[sid].dropna()
    if s_full.empty: continue
    last_val = s_full.iloc[-1]
    kpi(clean_label(id2title.get(sid, sid)), f"{last_val:,.2f}")
