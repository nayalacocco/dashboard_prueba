# pages/13_BCRA_Pasivos.py
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import inject_css, range_controls
from bcra_utils import (
    load_bcra_long,
    resample_series,
    nice_ticks,
    aligned_right_ticks_round,
)

st.set_page_config(page_title="BCRA – Pasivos remunerados", layout="wide")
inject_css()

st.title("🟦 Pasivos remunerados y absorción")

# -----------------------------
# Carga y normalización
# -----------------------------
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Corré el fetch (GitHub Actions) primero.")
    st.stop()

df["descripcion"] = df["descripcion"].fillna("").astype(str)

descs = sorted(df["descripcion"].unique().tolist())
descs_set = set(descs)

# -----------------------------
# Catálogo robusto de búsqueda
# -----------------------------
# INCLUIR pasivos remunerados (stocks en $)
PASIVOS_INC = re.compile(
    r"(\bpasivos?\s+remunerados?\b|\bleliq\b|\bpases?\s+pasivos?\b|\bpases?\b)",
    re.IGNORECASE,
)

# EXCLUIR tasas/variaciones/porcentajes para no confundir
PASIVOS_EXC = re.compile(
    r"(%|\bvar\.\b|\bvariaci[óo]n\b|\bpromedio\b|\bm[óo]vil\b|\bi\.a\.\b|\byoy\b|\bmom\b|\btasa\b|diaria|mensual)",
    re.IGNORECASE,
)

# Base monetaria (preferimos "total")
BASE_INC = re.compile(r"\bbase\s+monetaria\b", re.IGNORECASE)
BASE_PREF = re.compile(r"total", re.IGNORECASE)

# Candidatas de pasivos
pasivos_cands = [s for s in descs if PASIVOS_INC.search(s) and not PASIVOS_EXC.search(s)]
pasivos_cands = sorted(pasivos_cands)

# Candidatas de base
base_cands = [s for s in descs if BASE_INC.search(s)]
# Prioridad a las que contengan "total"
base_cands = sorted(base_cands, key=lambda s: (0 if BASE_PREF.search(s or "") else 1, s.lower()))

# Fallback manual si no se encuentra nada
if not pasivos_cands:
    fallback_pasivos = [
        "Pasivos remunerados (millones de pesos)",
        "Stock de LELIQs (millones de pesos)",
        "Stock de Pases Pasivos (millones de pesos)",
        "LELIQ + Pases Pasivos (millones de pesos)",
    ]
    pasivos_cands = [s for s in fallback_pasivos if s in descs_set]

if not base_cands:
    fallback_base = [
        "Base monetaria - Total (en millones de pesos)",
        "Base Monetaria – Total (en millones de pesos)",
        "Base Monetaria Total",
    ]
    base_cands = [s for s in fallback_base if s in descs_set]

if not pasivos_cands or not base_cands:
    st.warning("No pude identificar las series de Pasivos remunerados o Base monetaria.")
    st.stop()

# -----------------------------
# Selectores (si hay varias)
# -----------------------------
col_a, col_b = st.columns(2)
with col_a:
    pasivos_sel = st.selectbox("Serie de pasivos remunerados", pasivos_cands, index=0)
with col_b:
    base_sel = st.selectbox("Serie de base monetaria", base_cands, index=0)

# Wide (completo)
wfull = (
    df[df["descripcion"].isin([pasivos_sel, base_sel])]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

# -----------------------------
# Rango + Frecuencia
# -----------------------------
dmin, dmax = wfull.index.min(), wfull.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="pasivos")
w = wfull.loc[d_ini:d_fin]
freq = "D" if freq_label.startswith("Diaria") else "M"
if freq == "M":
    w = w.resample("M").last()
w = w.dropna(how="all")

if w.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# -----------------------------
# Doble eje Y con ticks alineados
#   - izquierda: pasivos
#   - derecha: base
# -----------------------------
left = w[pasivos_sel].dropna()
right = w[base_sel].dropna()

fig = go.Figure()

# Trazas
fig.add_trace(
    go.Scatter(
        x=left.index, y=left.values,
        mode="lines", name=pasivos_sel,
        line=dict(width=2, color="#60A5FA"),  # azul
        yaxis="y",
    )
)
fig.add_trace(
    go.Scatter(
        x=right.index, y=right.values,
        mode="lines", name=base_sel,
        line=dict(width=2, color="#F87171"),  # rojo
        yaxis="y2",
    )
)

# Eje izquierdo (ticks bonitos)
if not left.empty:
    lmin, lmax = float(np.nanmin(left.values)), float(np.nanmax(left.values))
    left_ticks = nice_ticks(lmin, lmax, max_ticks=7)
    y_range = [left_ticks[0], left_ticks[-1]] if left_ticks else [lmin, lmax]
else:
    left_ticks, y_range = [], [0, 1]

# Eje derecho alineado a la grilla del izquierdo
if not right.empty:
    rmin, rmax = float(np.nanmin(right.values)), float(np.nanmax(right.values))
    rticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)
else:
    rticks, (r0, r1) = [], (None, None)

fig.update_layout(
    template="plotly_dark",
    height=620,
    margin=dict(t=30, b=90, l=70, r=70),
    title="Stock (niveles)",
    legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center"),
)

fig.update_xaxes(
    title_text="Fecha",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
)

fig.update_yaxes(
    title_text="Eje izq",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
    tickmode="array" if left_ticks else "auto",
    tickvals=left_ticks if left_ticks else None,
    range=y_range if all(np.isfinite(y_range)) else None,
    zeroline=False,
)

fig.update_layout(
    yaxis2=dict(
        title="Eje der",
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

# -----------------------------
# Ratio Pasivos/Base
# -----------------------------
ratio = (w[pasivos_sel] / w[base_sel]).rename("Pasivos/Base").dropna()
if not ratio.empty:
    ratio_fig = go.Figure()
    ratio_fig.add_trace(
        go.Scatter(
            x=ratio.index, y=ratio.values, mode="lines",
            name="Pasivos/Base", line=dict(width=2, color="#34D399"),  # verde
        )
    )
    ratio_fig.update_layout(
        template="plotly_dark",
        height=500,
        margin=dict(t=30, b=70, l=70, r=70),
        title="Ratio Pasivos remunerados / Base monetaria",
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    )
    ratio_fig.update_xaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
    ratio_fig.update_yaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
    st.plotly_chart(ratio_fig, use_container_width=True)
else:
    st.info("No se pudo calcular el ratio Pasivos/Base para el rango elegido.")
