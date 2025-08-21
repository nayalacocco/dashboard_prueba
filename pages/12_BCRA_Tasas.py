# pages/12_BCRA_Tasas.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from ui import inject_css, range_controls, kpi_triplet, series_picker
from bcra_utils import (
    load_bcra_long,
    find_first,
    resample_series,
    compute_kpis,
)

st.set_page_config(page_title="BCRA – Política monetaria y tasas", layout="wide")
inject_css()
st.title("🟦 Política monetaria y tasas")

# =========================
# Datos
# =========================
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Corré el fetch (GitHub Actions) primero.")
    st.stop()

vars_all = sorted(df["descripcion"].dropna().unique().tolist())

# Sugerencias iniciales
tpm    = find_first(vars_all, "tasa", "política") or find_first(vars_all, "tasa de política")
pases  = find_first(vars_all, "tasa", "pases") or find_first(vars_all, "operaciones", "pase")
badlar = find_first(vars_all, "badlar")
pfijo  = find_first(vars_all, "plazo", "fijo")
base   = find_first(vars_all, "base", "monetaria")

opciones = vars_all
predef = [x for x in [badlar, base, pases, tpm, pfijo] if x and x in opciones][:3]

# Selector futurista (chips + botón limpiar)
sel = series_picker(
    opciones,
    default=predef if predef else None,
    max_selections=3,
    key="tasas",
    title="Elegí hasta 3 series",
    subtitle="Podés combinar tasas (%) con agregados o reservas; si mezclás, usamos doble eje.",
)
if not sel:
    st.info("Elegí al menos una serie para comenzar.")
    st.stop()

# Wide completo
wide_full = (
    df[df["descripcion"].isin(sel)]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

# =========================
# Rango + frecuencia (última acción gana)
# =========================
dmin, dmax = wide_full.index.min(), wide_full.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="tasas")
freq = "D" if freq_label.startswith("Diaria") else "M"

wide_vis = wide_full.loc[d_ini:d_fin]
if freq == "M":
    wide_vis = wide_vis.resample("M").last()
wide_vis = wide_vis.dropna(how="all")
if wide_vis.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# =========================
# Heurística: izq (tasas/%) vs der (niveles)
# =========================
def is_percent_name(name: str) -> bool:
    s = name.lower()
    tokens = ["%", "en %", "tna", "tea", "variación", "variacion", "yoy", "mom", "interanual", "mensual"]
    return any(t in s for t in tokens)

left_series  = [n for n in sel if is_percent_name(n)]
right_series = [n for n in sel if n not in left_series]
if not left_series:  # si no hay ninguna tasa, todo a la izquierda (sin eje derecho)
    left_series = sel[:]
    right_series = []

# =========================
# Figura
# =========================
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

legend_left  = []  # (label, color)
legend_right = []  # (label, color)

# Izquierda
for i, name in enumerate(left_series):
    s = wide_vis[name].dropna()
    if s.empty:
        continue
    color = palette[i % len(palette)]
    legend_left.append((name, color))
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=name,
            line=dict(width=2, color=color),
            yaxis="y",
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

# Derecha (nombres sin '[eje derecho]')
for j, name in enumerate(right_series):
    s = wide_vis[name].dropna()
    if s.empty:
        continue
    color = palette[(len(left_series) + j) % len(palette)]
    legend_right.append((name, color))
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=name,
            line=dict(width=2, color=color),
            yaxis="y2",
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

# Layout base
fig.update_layout(
    template="atlas_dark",
    height=620,
    margin=dict(t=30, b=120, l=70, r=90),
    showlegend=False,   # leyenda nativa off
    uirevision=None,    # siempre re-encuadra
)

fig.update_xaxes(
    title_text="Fecha",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
)

left_is_percent = any(is_percent_name(n) for n in left_series) if left_series else False
fig.update_yaxes(
    title_text="Eje izq",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
    showgrid=True, gridcolor="#1F2937",
    autorange=True,
    tickmode="auto",
    tickformat=(".0f" if left_is_percent else "~s"),
    zeroline=False,
)

if right_series:
    fig.update_layout(
        yaxis2=dict(
            title="Eje der",
            overlaying="y", side="right",
            showline=True, linewidth=1, linecolor="#E5E7EB",
            showgrid=False,
            autorange=True,
            tickmode="auto",
            tickformat="~s",
            zeroline=False,
        )
    )

# =========================
# Escala logarítmica (visual)
# =========================
log_col1, log_col2, _ = st.columns([1,1,2])
with log_col1:
    log_left = st.toggle("Escala log (eje izq)", value=False, key="log_left_tasas")
with log_col2:
    log_right = st.toggle("Escala log (eje der)", value=False, key="log_right_tasas", disabled=(len(right_series)==0))

if log_left:
    fig.update_yaxes(type="log")
if log_right and right_series:
    fig.update_layout(yaxis2=dict(type="log"))

st.plotly_chart(fig, use_container_width=True)

# =========================
# Leyenda custom: izquierda vs derecha (sin “[eje derecho]”)
# =========================
if legend_left or legend_right:
    rows_html = []
    if legend_left:
        left_items = "".join(
            f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>'
            for lbl, c in legend_left
        )
        rows_html.append(f'<div class="col"><div class="hdr">Eje izquierdo</div>{left_items}</div>')
    if legend_right:
        right_items = "".join(
            f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>'
            for lbl, c in legend_right
        )
        rows_html.append(f'<div class="col right"><div class="hdr">Eje derecho</div>{right_items}</div>')

    st.markdown(
        "<div class='split-legend'>" + ("".join(rows_html)) + "</div>",
        unsafe_allow_html=True,
    )

# =========================
# KPIs por serie (tripleta)
# =========================
def kpis_for(name: str, color: str):
    serie_full = (
        df[df["descripcion"] == name]
        .set_index("fecha")["valor"]
        .sort_index()
        .astype(float)
    )
    serie_visible = resample_series(
        wide_full[name].loc[d_ini:d_fin].dropna(),
        freq=("D" if freq_label.startswith("Diaria") else "M"),
        how="last",
    ).dropna()

    mom, yoy, d_per = compute_kpis(serie_full, serie_visible)
    kpi_triplet(
        title=name,
        color=color,
        mom=mom, yoy=yoy, d_per=d_per,
        tip_mom="Variación del último dato mensual vs el mes previo (fin de mes).",
        tip_yoy="Variación del último dato mensual vs el mismo mes de hace 12 meses.",
        tip_per="Variación entre primer y último dato del rango visible (frecuencia elegida).",
    )

palette_cycle = ["#60A5FA", "#F87171", "#34D399"]
for idx, name in enumerate(sel):
    kpis_for(name, palette_cycle[idx % len(palette_cycle)])
