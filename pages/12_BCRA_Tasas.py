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

# Detectamos algunas tasas y una monetaria como ejemplo
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
    help="Podés combinar tasas (en %) con agregados o reservas. Si las escalas difieren mucho, se usa doble eje Y.",
    key="tasas_sel",
)

if not sel:
    st.info("Elegí al menos una serie para comenzar.")
    st.stop()

# Pivot con todas las seleccionadas
wide_full = (
    df[df["descripcion"].isin(sel)]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

# Rango + frecuencia
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
# Heurística de ejes
# =========================
# 1) Primera serie (sel[0]) define el eje izquierdo
# 2) Cada serie siguiente va al eje cuya escala sea más parecida;
#    si la relación de rangos con el eje izq es > THRESH, mandamos al eje derecho.
THRESH = 5.0

def _range(s: pd.Series) -> float:
    s = s.dropna()
    if len(s) == 0:
        return 0.0
    return float(s.max() - s.min())

left_series = [sel[0]]
right_series = []

left_range = _range(wide_vis[sel[0]])
right_range = None  # lo definimos si aparece algo en right

for name in sel[1:]:
    r = _range(wide_vis[name])
    if left_range == 0:
        left_series.append(name)
    else:
        if r / max(left_range, 1e-12) > THRESH:
            right_series.append(name)
            right_range = r if right_range is None else max(right_range, r)
        else:
            left_series.append(name)
            left_range = max(left_range, r)

# Si por alguna razón no hay nada a la izquierda, muevo una del right
if not left_series and right_series:
    left_series.append(right_series.pop(0))

# =========================
# Figura
# =========================
fig = go.Figure()

palette = [
    "#60A5FA",  # azul
    "#F87171",  # rojo
    "#34D399",  # verde
]

# Left axis traces
for i, name in enumerate(left_series):
    s = wide_vis[name].dropna()
    if s.empty:
        continue
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=name, line=dict(width=2, color=palette[i % len(palette)]),
            yaxis="y"
        )
    )

# Right axis traces
for j, name in enumerate(right_series):
    s = wide_vis[name].dropna()
    if s.empty:
        continue
    color = palette[(len(left_series) + j) % len(palette)]
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=name, line=dict(width=2, color=color),
            yaxis="y2"
        )
    )

# Rango y ticks del eje izquierdo (bonitos)
if left_series:
    left_vals = pd.concat([wide_vis[n].dropna() for n in left_series], axis=0)
    lmin, lmax = float(left_vals.min()), float(left_vals.max())
    left_ticks = nice_ticks(lmin, lmax, max_ticks=7)
    y_range = [left_ticks[0], left_ticks[-1]] if left_ticks else [lmin, lmax]
else:
    left_ticks, y_range = [], [0, 1]

# Rango y ticks del eje derecho alineados a la grilla del izquierdo
if right_series:
    right_vals = pd.concat([wide_vis[n].dropna() for n in right_series], axis=0)
    rmin, rmax = float(right_vals.min()), float(right_vals.max())
    rticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)
else:
    rticks, (r0, r1) = [], (None, None)

fig.update_layout(
    template="plotly_dark",
    height=620,
    margin=dict(t=30, b=90, l=70, r=70),
    legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center"),
)

fig.update_xaxes(
    title_text="Fecha",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
)

# Eje izquierdo
fig.update_yaxes(
    title_text="Eje izq",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
    tickmode="array" if left_ticks else "auto",
    tickvals=left_ticks if left_ticks else None,
    range=y_range if all(np.isfinite(y_range)) else None,
    zeroline=False,
)

# Eje derecho (solo si hay series)
if right_series:
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

# =========================
# KPIs (sobre la PRIMERA serie seleccionada)
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
    kpi("Mensual (MoM)", fmt(mom),
        help_text="Variación del último dato mensual vs el mes previo (fin de mes).")
with c2:
    kpi("Interanual (YoY)", fmt(yoy),
        help_text="Variación del último dato mensual vs el mismo mes de hace 12 meses.")
with c3:
    kpi("Δ en el período", fmt(d_per),
        help_text="Variación entre primer y último dato del rango visible (frecuencia elegida).")
