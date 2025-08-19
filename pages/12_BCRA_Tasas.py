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

# Datos
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
    help="Podés combinar tasas (en %) con agregados o reservas. Si las escalas difieren mucho, se usa doble eje Y.",
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

# Rango + frecuencia (auto-prioridad)
dmin, dmax = wide_full.index.min(), wide_full.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="tasas", priority="auto")
freq = "D" if freq_label.startswith("Diaria") else "M"

wide_vis = wide_full.loc[d_ini:d_fin]
if freq == "M":
    wide_vis = wide_vis.resample("M").last()
wide_vis = wide_vis.dropna(how="all")
if wide_vis.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# Doble eje heurístico
THRESH = 5.0
def _range(s: pd.Series) -> float:
    s = s.dropna()
    return 0.0 if len(s) == 0 else float(s.max() - s.min())

left_series = [sel[0]]
right_series, left_range, right_range = [], _range(wide_vis[sel[0]]), None
for name in sel[1:]:
    r = _range(wide_vis[name])
    if left_range == 0:
        left_series.append(name); left_range = r
    else:
        if r / max(left_range, 1e-12) > THRESH:
            right_series.append(name)
            right_range = r if right_range is None else max(right_range, r)
        else:
            left_series.append(name); left_range = max(left_range, r)
if not left_series and right_series:
    left_series.append(right_series.pop(0))

# Figura
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

def looks_like_percent(name: str) -> bool:
    s = name.lower()
    return ("% " in s) or ("en %" in s) or (" tna" in s) or (" tea" in s) or ("por ciento" in s)

for i, name in enumerate(left_series):
    s = wide_vis[name].dropna()
    if s.empty: continue
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=name, line=dict(width=2, color=palette[i % len(palette)]),
        yaxis="y", hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

for j, name in enumerate(right_series):
    s = wide_vis[name].dropna()
    if s.empty: continue
    color = palette[(len(left_series) + j) % len(palette)]
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=f"{name} [eje derecho]", line=dict(width=2, color=color),
        yaxis="y2", hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

# Rangos con padding
left_ticks, y_range = [], None
if left_series:
    left_vals = pd.concat([wide_vis[n].dropna() for n in left_series], axis=0)
    lmin, lmax = float(left_vals.min()), float(left_vals.max())
    if lmax == lmin:
        pad = max(1.0, abs(lmin) * 0.05)
        y_range = [lmin - pad, lmax + pad]
    else:
        span = lmax - lmin
        pad = max(span * 0.05, 1e-9)  # 5% o mínimo
        lmin_p, lmax_p = lmin - pad, lmax + pad
        lt = nice_ticks(lmin_p, lmax_p, max_ticks=7)
        left_ticks = lt
        y_range = [lt[0], lt[-1]] if lt else [lmin_p, lmax_p]

rticks, rrange = [], (None, None)
if right_series:
    right_vals = pd.concat([wide_vis[n].dropna() for n in right_series], axis=0)
    rmin_raw, rmax_raw = float(right_vals.min()), float(right_vals.max())
    span_r = rmax_raw - rmin_raw
    pad_r = max(span_r * 0.05, 1e-9)
    rmin, rmax = rmin_raw - pad_r, rmax_raw + pad_r

    rticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)
    # garantizar inclusión
    if r0 is not None and r0 > rmin:
        shift = r0 - rmin
        r0 -= shift; r1 -= shift; rticks = [t - shift for t in rticks]
    if r1 is not None and r1 < rmax:
        add = rmax - r1
        r1 += add; rticks = [t + add for t in rticks]
    # nada de negativos si datos ≥0
    if rmin_raw >= 0 and r0 is not None and r0 < 0:
        rticks = [t - r0 for t in rticks]; r1 = r1 - r0; r0 = 0.0
    rrange = (r0, r1)

def si_label(x: float) -> str:
    if x is None or not np.isfinite(x): return ""
    sign = "-" if x < 0 else ""
    v = abs(x)
    if v >= 1e9:  txt = f"{v/1e9:.0f}B" if v/1e9 >= 10 else f"{v/1e9:.1f}B"
    elif v >= 1e6: txt = f"{v/1e6:.0f}M" if v/1e6 >= 10 else f"{v/1e6:.1f}M"
    elif v >= 1e3: txt = f"{v/1e3:.0f}K" if v/1e3 >= 10 else f"{v/1e3:.1f}K"
    else:         txt = f"{v:.0f}"
    return (sign + txt).replace(".0K","K").replace(".0M","M").replace(".0B","B")

right_ticktext = [si_label(v) for v in rticks] if rticks else []

# Layout
uirev = f"{d_ini}-{d_fin}-{freq}-{'|'.join(sel)}"
fig.update_layout(
    template="plotly_dark",
    height=620,
    margin=dict(t=30, b=90, l=70, r=90),
    legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center"),
    uirevision=uirev,
)
fig.update_xaxes(title_text="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")

left_is_percent = any(looks_like_percent(n) for n in left_series) if left_series else False
left_tickformat = ".0f" if left_is_percent else "~s"

fig.update_yaxes(
    title_text="Eje izq",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
    showgrid=True, gridcolor="#1F2937",
    tickmode="array" if left_ticks else "auto",
    tickvals=left_ticks if left_ticks else None,
    tickformat=left_tickformat,
    range=y_range if (y_range and np.isfinite(y_range[0]) and np.isfinite(y_range[1])) else None,
    autorange=False if y_range else True,
    zeroline=False,
)

if right_series:
    r0, r1 = rrange
    fig.update_layout(
        yaxis2=dict(
            title="Eje der",
            overlaying="y", side="right",
            showgrid=False,
            tickmode="array" if rticks else "auto",
            tickvals=rticks if rticks else None,
            ticktext=right_ticktext if rticks else None,
            range=[r0, r1] if (r0 is not None and r1 is not None) else None,
            autorange=False if (r0 is not None and r1 is not None) else True,
            showline=True, linewidth=1, linecolor="#E5E7EB",
            zeroline=False,
        )
    )

st.plotly_chart(fig, use_container_width=True)

# KPIs
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
with c1: kpi("Mensual (MoM)", fmt(mom), help_text="Variación del último dato mensual vs el mes previo (fin de mes).")
with c2: kpi("Interanual (YoY)", fmt(yoy), help_text="Variación del último dato mensual vs el mismo mes de hace 12 meses.")
with c3: kpi("Δ en el período", fmt(d_per), help_text="Variación entre primer y último dato del rango visible (frecuencia elegida).")
