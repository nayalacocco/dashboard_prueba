# pages/14_BCRA_Reservas.py
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import inject_css, range_controls
from bcra_utils import (
    load_bcra_long,
    nice_ticks,
    aligned_right_ticks_round,
)

st.set_page_config(page_title="BCRA – Reservas y Tipo de Cambio", layout="wide")
inject_css()

st.title("🟦 Reservas y tipo de cambio")

# -----------------------------
# Carga y normalización
# -----------------------------
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Corré el fetch primero.")
    st.stop()

df["descripcion"] = df["descripcion"].fillna("").astype(str)
descs = sorted(df["descripcion"].unique().tolist())

# -----------------------------
# Candidatos de series
# -----------------------------
RESERVAS_INC = re.compile(r"\breservas?\b", re.IGNORECASE)
USD_HINT = re.compile(r"\busd\b|d[oó]lares", re.IGNORECASE)

res_cands = [s for s in descs if RESERVAS_INC.search(s)]
res_cands = sorted(res_cands, key=lambda s: (0 if USD_HINT.search(s or "") else 1, s.lower()))
if not res_cands:
    st.warning("No encontré series de Reservas en el catálogo.")
    st.stop()

TC_INC = re.compile(r"(tipo\s+de\s+cambio|mayorista|comprador|vendedor|a\s*3500|referencia)", re.IGNORECASE)
TC_EXC = re.compile(r"%|variaci[oó]n|promedio|m[óo]vil|i\.a\.|yoy|mom|tasa", re.IGNORECASE)

tc_cands = [s for s in descs if TC_INC.search(s) and not TC_EXC.search(s)]
tc_cands = sorted(
    tc_cands,
    key=lambda s: (
        0 if (re.search("mayorista", s, re.I) and re.search("referencia|a\s*3500", s, re.I)) else 1,
        s.lower(),
    ),
)
if not tc_cands:
    st.warning("No encontré series de Tipo de cambio en el catálogo.")
    st.stop()

# -----------------------------
# Selectores de series
# -----------------------------
col_a, col_b = st.columns(2)
with col_a:
    reservas_sel = st.selectbox("Serie de reservas", res_cands, index=0)
with col_b:
    tc_sel = st.selectbox("Serie de tipo de cambio", tc_cands, index=0)

# Wide con ambas
wide_all = (
    df[df["descripcion"].isin([reservas_sel, tc_sel])]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
    .dropna(how="all")
)
if wide_all.empty:
    st.warning("No hay datos para graficar.")
    st.stop()

# -----------------------------
# Controles de rango + gobierno + frecuencia (consistentes)
# -----------------------------
dmin, dmax = wide_all.index.min(), wide_all.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="reservas_tc")

freq = "D" if freq_label.startswith("Diaria") else "M"
w = wide_all.loc[d_ini:d_fin]
if freq == "M":
    w = w.resample("M").last()
w = w.dropna(how="all")
if w.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

left = w[reservas_sel].dropna()
right = w[tc_sel].dropna()

# -----------------------------
# Títulos breves para ejes
# -----------------------------
def short_title(desc: str, side: str) -> str:
    base = re.split(r"\(|–|-", desc)[0].strip()
    if side == "left":
        return "Reservas (USD)" if re.search(r"usd|d[oó]lares", desc, re.I) else base
    return "Tipo de cambio ($/USD)" if re.search(r"cambio|a\s*3500|mayorista|vendedor|comprador", desc, re.I) else base

# -----------------------------
# Figura SIEMPRE con doble eje
# -----------------------------
fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=left.index, y=left.values,
        mode="lines", name=reservas_sel,
        line=dict(width=2, color="#60A5FA"),
        yaxis="y"
    )
)
fig.add_trace(
    go.Scatter(
        x=right.index, y=right.values,
        mode="lines", name=tc_sel,
        line=dict(width=2, color="#34D399"),
        yaxis="y2"
    )
)

# Eje izq: ticks “bonitos”
if not left.empty:
    lmin, lmax = float(np.nanmin(left.values)), float(np.nanmax(left.values))
    left_ticks = nice_ticks(lmin, lmax, max_ticks=7)
    y_range = [left_ticks[0], left_ticks[-1]] if left_ticks else [lmin, lmax]
else:
    left_ticks, y_range = [], [0, 1]

# Eje der: alineado a la grilla del izq
if not right.empty:
    rmin, rmax = float(np.nanmin(right.values)), float(np.nanmax(right.values))
    rticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)
else:
    rticks, (r0, r1) = [], (None, None)

fig.update_layout(
    template="plotly_dark",
    height=640,
    margin=dict(t=30, b=90, l=80, r=80),
    legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center"),
)

fig.update_xaxes(
    title_text="Fecha",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
)

fig.update_yaxes(
    title_text=short_title(reservas_sel, "left"),
    title_standoff=12,
    automargin=True,
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
    tickmode="array" if left_ticks else "auto",
    tickvals=left_ticks if left_ticks else None,
    range=y_range if all(np.isfinite(y_range)) else None,
    zeroline=False,
)

fig.update_layout(
    yaxis2=dict(
        title=short_title(tc_sel, "right"),
        title_standoff=12,
        overlaying="y",
        side="right",
        tickmode="array" if rticks else "auto",
        tickvals=rticks if rticks else None,
        range=[r0, r1] if (r0 is not None and r1 is not None) else None,
        showline=True, linewidth=1, linecolor="#E5E7EB",
        zeroline=False,
    )
)

st.plotly_chart(fig, use_container_width=True)
