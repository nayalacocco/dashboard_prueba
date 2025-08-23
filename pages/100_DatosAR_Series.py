# pages/100_DatosAR_Series.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from ui import inject_css, range_controls, clean_label, looks_percent, kpi_quad
from datosar_utils import (
    load_datosar_long,
    publishers_datasets_series,
    api_values,           # para recargar una serie puntual si hace falta
)

st.set_page_config(page_title="Series de Datos Argentina", layout="wide")
inject_css()
st.title("📈 Series de Datos Argentina")

st.caption(
    "Catálogo local armado desde la API de Series de Tiempo (datos.gob.ar). "
    "Si no ves datos, corré el fetch nocturno o el workflow manual."
)

# ---------- Carga local ----------
df_long = load_datosar_long()
if df_long.empty:
    st.warning("Todavía no hay datos locales. Corré `scripts/fetch_datosar.py` o el workflow.")
    st.stop()

pubs, by_pub, by_key = publishers_datasets_series()

# ---------- UI de catálogo ----------
with st.expander("📚 Explorar catálogo (publicador → dataset → serie)", expanded=True):
    c1, c2, c3 = st.columns([1.2, 1.2, 2])
    with c1:
        pub = st.selectbox("Publicador", pubs, index=0 if pubs else None)
    with c2:
        ds_list = by_pub.get(pub, [])
        ds = st.selectbox("Dataset", ds_list, index=0 if ds_list else None)
    with c3:
        series_objs = by_key.get((pub, ds), [])
        titles = [f"{clean_label(s.title or s.id)}  ·  ({s.id})" for s in series_objs]
        sel_idx = st.multiselect("Series (podés elegir hasta 3)", list(range(len(series_objs))), max_selections=3, default=list(range(min(3, len(series_objs)))))
        sel_series = [series_objs[i] for i in sel_idx]

if not sel_series:
    st.info("Elegí al menos una serie.")
    st.stop()

# ---------- Construyo wide visible ----------
ids_sel = [s.id for s in sel_series]
wide_full = (
    df_long[df_long["id"].isin(ids_sel)]
    .pivot(index="fecha", columns="id", values="valor")
    .sort_index()
)

dmin, dmax = wide_full.index.min().date(), wide_full.index.max().date()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="datosar", show_government=False)
wide_vis = wide_full.loc[str(d_ini):str(d_fin)].copy()

if freq_label.startswith("Mensual"):
    wide_vis = wide_vis.resample("M").last()

wide_vis = wide_vis.dropna(how="all")
if wide_vis.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# ---------- Grafico ----------
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]
for i, sid in enumerate(ids_sel):
    s = wide_vis[sid].dropna()
    if s.empty: 
        continue
    color = palette[i % len(palette)]
    label = clean_label(next((x.title for x in sel_series if x.id == sid), sid))
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=label, line=dict(width=2, color=color),
        hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

fig.update_layout(template="atlas_dark", height=520, margin=dict(t=30, b=60, l=70, r=40), showlegend=True)
fig.update_xaxes(title_text="Fecha")
fig.update_yaxes(title_text="Valor", showgrid=True, gridcolor="#1F2937")

st.plotly_chart(fig, use_container_width=True)

# ---------- KPIs (cuádruple: último + MoM + YoY + Δ período) ----------
def compute_kpis_from_series(s: pd.Series) -> tuple[float|None, float|None, float|None, float|None]:
    s = s.dropna()
    if s.empty:
        return None, None, None, None
    last = s.iloc[-1]
    mom = (s.resample("M").last().pct_change().iloc[-1]*100) if len(s) > 1 else None
    yoy = (s.resample("M").last().pct_change(12).iloc[-1]*100) if len(s) > 12 else None
    delta = (s.iloc[-1] - s.iloc[0]) / (abs(s.iloc[0]) if s.iloc[0] else 1) * 100 if len(s) > 1 else None
    return last, mom, yoy, delta

palette_cycle = ["#60A5FA", "#F87171", "#34D399"]
for i, sdesc in enumerate(sel_series):
    sid = sdesc.id
    last, mom, yoy, dper = compute_kpis_from_series(wide_vis[sid])
    kpi_quad(
        title=clean_label(sdesc.title or sid),
        color=palette_cycle[i % len(palette_cycle)],
        last_value=last,
        is_percent=looks_percent(sdesc.title or ""),
        mom=mom, yoy=yoy, d_per=dper,
        tip_last="Último dato visible en el rango elegido",
        tip_mom="Variación mensual del dato mensual (fin de mes).",
        tip_yoy="Variación interanual del dato mensual.",
        tip_per="Δ entre el primer y el último dato del rango visible.",
    )
