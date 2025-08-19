# pages/12_BCRA_Tasas.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from ui import inject_css, range_controls, kpi
from bcra_utils import (
    load_bcra_long,
    find_first,
    resample_series,
    compute_kpis,
    nice_ticks,
    aligned_right_ticks_round,
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

tpm    = find_first(vars_all, "tasa", "política") or find_first(vars_all, "tasa de política")
pases  = find_first(vars_all, "tasa", "pases") or find_first(vars_all, "operaciones", "pase")
badlar = find_first(vars_all, "badlar")
pfijo  = find_first(vars_all, "plazo", "fijo")
base   = find_first(vars_all, "base", "monetaria")

opciones = vars_all
predef = [x for x in [badlar, base, pases, tpm, pfijo] if x and x in opciones][:3]

sel = st.multiselect(
    "Elegí hasta 3 series",
    opciones,
    default=predef if predef else None,
    max_selections=3,
    help="Podés combinar tasas (en %) con agregados o reservas. Si hay tasas y niveles juntos se usa doble eje Y.",
    key="tasas_sel",
)
if not sel:
    st.info("Elegí al menos una serie para comenzar.")
    st.stop()

wide_full = (
    df[df["descripcion"].isin(sel)]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

# =========================
# Rango + frecuencia
#  - la función range_controls ya hace: si tocas Rango rápido, pisa Gobierno y lo limpia
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
# Clasificación por tipo → define ejes
# =========================
def is_percent_name(name: str) -> bool:
    s = name.lower()
    tokens = ["%", "en %", " por ciento", "tna", "tea", "variación", "variacion", "yoy", "mom", "interanual", "mensual"]
    return any(t in s for t in tokens)

left_series  = [n for n in sel if is_percent_name(n)]          # tasas / variaciones
right_series = [n for n in sel if n not in left_series]        # niveles (base, reservas, etc.)

use_y2 = len(left_series) > 0 and len(right_series) > 0
if not use_y2:
    left_series = sel.copy()
    right_series = []

# =========================
# Figura
# =========================
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

for i, name in enumerate(left_series):
    s = wide_vis[name].dropna()
    if s.empty: 
        continue
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=name, line=dict(width=2, color=palette[i % len(palette)]),
        yaxis="y", hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

for j, name in enumerate(right_series):
    s = wide_vis[name].dropna()
    if s.empty: 
        continue
    color = palette[(len(left_series) + j) % len(palette)]
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=f"{name} [eje derecho]", line=dict(width=2, color=color),
        yaxis="y2", hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

# =========================
# Rango y ticks (FIX: el rango ya NO depende de los ticks “lindos”)
# =========================
def with_pad(vmin: float, vmax: float, pct: float = 0.05):
    """Padding simétrico del 5% (mínimo epsilon) para que nada quede recortado."""
    if not np.isfinite(vmin) or not np.isfinite(vmax):
        return vmin, vmax
    if vmax == vmin:
        pad = max(1.0, abs(vmin) * pct)
        return vmin - pad, vmax + pad
    span = vmax - vmin
    pad = max(span * pct, 1e-9)
    return vmin - pad, vmax + pad

# --- Eje izquierdo
left_ticks, y_range = None, None
if left_series:
    left_vals = pd.concat([wide_vis[n].dropna() for n in left_series], axis=0)
    lmin, lmax = float(left_vals.min()), float(left_vals.max())
    lmin_p, lmax_p = with_pad(lmin, lmax)
    y_range = [lmin_p, lmax_p]                     # <-- RANGO REAL con padding (no los ticks)
    left_ticks = nice_ticks(lmin_p, lmax_p, max_ticks=7)

# --- Eje derecho
rticks, r0, r1 = None, None, None
right_ticktext = None
if use_y2:
    right_vals = pd.concat([wide_vis[n].dropna() for n in right_series], axis=0)
    rmin_raw, rmax_raw = float(right_vals.min()), float(right_vals.max())
    rmin_p, rmax_p = with_pad(rmin_raw, rmax_raw)

    # alineamos con la grilla del izq, pero el RANGO es el real con padding
    rticks, (r0, r1) = aligned_right_ticks_round(left_ticks or [], rmin_p, rmax_p)

    # garantía de que los ticks caen dentro del rango (solo por estética)
    if rticks:
        rticks = [t for t in rticks if (t >= rmin_p and t <= rmax_p)]
        if not rticks:  # fallback
            rticks = nice_ticks(rmin_p, rmax_p, max_ticks=6)

    # si todos los datos del derecho son >= 0, pegamos piso en 0
    if rmin_raw >= 0:
        rmin_p = max(0.0, rmin_p)

    # etiquetas K/M/B
    def si_label(x: float) -> str:
        if x is None or not np.isfinite(x): 
            return ""
        sign = "-" if x < 0 else ""
        v = abs(x)
        if v >= 1e9:  txt = f"{v/1e9:.1f}B"
        elif v >= 1e6: txt = f"{v/1e6:.1f}M"
        elif v >= 1e3: txt = f"{v/1e3:.1f}K"
        else:         txt = f"{v:.0f}"
        return (sign + txt).replace(".0K","K").replace(".0M","M").replace(".0B","B")
    right_ticktext = [si_label(v) for v in (rticks or [])]

# =========================
# Layout
# =========================
uirev = f"{d_ini}-{d_fin}-{freq}-{'|'.join(sel)}"
fig.update_layout(
    template="plotly_dark",
    height=620,
    margin=dict(t=30, b=90, l=70, r=90),
    legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center"),
    uirevision=uirev,  # evita “saltos” al tocar controles
)
fig.update_xaxes(title_text="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")

left_is_percent = bool(left_series and any(is_percent_name(n) for n in left_series))
fig.update_yaxes(
    title_text="Eje izq",
    showline=True, linewidth=1, linecolor="#E5E7EB",
    showgrid=True, gridcolor="#1F2937",
    ticks="outside",
    tickmode="array" if left_ticks else "auto",
    tickvals=left_ticks if left_ticks else None,
    tickformat=(".0f" if left_is_percent else "~s"),
    range=y_range if y_range else None,
    autorange=False if y_range else True,
    zeroline=False,
)

if use_y2:
    fig.update_layout(
        yaxis2=dict(
            title="Eje der",
            overlaying="y",
            side="right",
            showline=True, linewidth=1, linecolor="#E5E7EB",
            showgrid=False,
            tickmode="array" if rticks else "auto",
            tickvals=rticks if rticks else None,
            ticktext=right_ticktext if rticks else None,
            range=[rmin_p, rmax_p],
            autorange=False,
            zeroline=False,
        )
    )

st.plotly_chart(fig, use_container_width=True)

# =========================
# KPIs (sobre la primera seleccionada)
# =========================
principal = sel[0]
serie_full = (
    df[df["descripcion"] == principal]
    .set_index("fecha")["valor"]
    .sort_index()
    .astype(float)
)
serie_visible = resample_series(
    wide_full[principal].loc[d_ini:d_fin].dropna(),
    freq=("D" if freq_label.startswith("Diaria") else "M"),
    how="last",
).dropna()

mom, yoy, d_per = compute_kpis(serie_full, serie_visible)
fmt = lambda x: ("—" if x is None or pd.isna(x) else f"{x:,.2f}%")
c1, c2, c3 = st.columns(3)
with c1:
    kpi("Mensual (MoM)", fmt(mom), help_text="Variación del último dato mensual vs el mes previo (fin de mes).")
with c2:
    kpi("Interanual (YoY)", fmt(yoy), help_text="Variación del último dato mensual vs el mismo mes de hace 12 meses.")
with c3:
    kpi("Δ en el período", fmt(d_per), help_text="Variación entre primer y último dato del rango visible (frecuencia elegida).")
