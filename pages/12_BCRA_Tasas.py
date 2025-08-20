# pages/12_BCRA_Tasas.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from ui import inject_css, range_controls, kpi_triplet
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

# Algunas sugeridas para que aparezca algo por defecto
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

# Pivot de las seleccionadas
wide_full = (
    df[df["descripcion"].isin(sel)]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

# =========================
# Rango + frecuencia (con prioridad 'última acción gana')
# =========================
dmin, dmax = wide_full.index.min(), wide_full.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="tasas", show_government=True)
freq = "D" if freq_label.startswith("Diaria") else "M"

wide_vis = wide_full.loc[d_ini:d_fin]
if freq == "M":
    wide_vis = wide_vis.resample("M").last()
wide_vis = wide_vis.dropna(how="all")
if wide_vis.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# =========================
# Clasificación de series para ejes
# =========================
def is_percent_name(name: str) -> bool:
    s = name.lower()
    tokens = ["%", "en %", " por ciento", "tna", "tea", "variación", "variacion", "yoy", "mom", "interanual", "mensual"]
    return any(t in s for t in tokens)

left_series  = [n for n in sel if is_percent_name(n)]
right_series = [n for n in sel if n not in left_series]

# si quedaron todas de un lado, desactivamos y2
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
        name=name,
        line=dict(width=2, color=palette[i % len(palette)]),
        yaxis="y",
        hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

for j, name in enumerate(right_series):
    s = wide_vis[name].dropna()
    if s.empty:
        continue
    color = palette[(len(left_series) + j) % len(palette)]
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=f"{name} [eje derecho]",
        line=dict(width=2, color=color),
        yaxis="y2",
        hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

# =========================
# Rangos y ticks “bonitos” + padding + eje derecho alineado
# =========================
def with_pad(vmin: float, vmax: float, pct: float = 0.05):
    if not np.isfinite(vmin) or not np.isfinite(vmax):
        return vmin, vmax
    if vmax == vmin:
        pad = max(1.0, abs(vmin) * pct)
        return vmin - pad, vmax + pad
    span = vmax - vmin
    pad = max(span * pct, 1e-9)
    return vmin - pad, vmax + pad

# Izquierdo
left_ticks, y_range = [], None
if left_series:
    left_vals = pd.concat([wide_vis[n].dropna() for n in left_series], axis=0)
    lmin, lmax = float(left_vals.min()), float(left_vals.max())
    lmin_p, lmax_p = with_pad(lmin, lmax)
    lt = nice_ticks(lmin_p, lmax_p, max_ticks=7)
    left_ticks = lt or [lmin_p, lmax_p]
    y_range = [left_ticks[0], left_ticks[-1]] if lt else [lmin_p, lmax_p]

# Derecho
rticks, rrange = [], (None, None)
if use_y2:
    right_vals = pd.concat([wide_vis[n].dropna() for n in right_series], axis=0)
    rmin_raw, rmax_raw = float(right_vals.min()), float(right_vals.max())
    rmin, rmax = with_pad(rmin_raw, rmax_raw)
    rticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)

    # asegurar inclusión de extremos con el padding
    if r0 is not None and r0 > rmin:
        shift = r0 - rmin
        r0 -= shift; r1 -= shift; rticks = [t - shift for t in rticks]
    if r1 is not None and r1 < rmax:
        add = rmax - r1
        r1 += add; rticks = [t + add for t in rticks]
    # si todo es positivo, evitamos que el primer tick sea negativo luego de redondear
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

# =========================
# Layout
# =========================
uirev = f"{d_ini}-{d_fin}-{freq}-{'|'.join(sel)}"
fig.update_layout(
    template="plotly_dark",
    height=620,
    margin=dict(t=30, b=90, l=70, r=90),
    legend=dict(orientation="h", y=-0.28, x=0.5, xanchor="center"),
    uirevision=uirev,  # evita autoscale al interactuar con leyenda
)
fig.update_xaxes(title_text="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")

# Izquierdo (si es tasa, mostramos números plain; si no, abreviamos con ~s)
left_is_percent = True if left_series and any(is_percent_name(n) for n in left_series) else False
fig.update_yaxes(
    title_text="Eje izq",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
    showgrid=True, gridcolor="#1F2937",
    tickmode="array" if left_ticks else "auto",
    tickvals=left_ticks if left_ticks else None,
    tickformat=(".0f" if left_is_percent else "~s"),
    range=y_range if (y_range and np.isfinite(y_range[0]) and np.isfinite(y_range[1])) else None,
    autorange=False if y_range else True,
    zeroline=False,
)

if use_y2:
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

# =========================
# KPIs – un bloque por serie
# =========================
# orden de impresión igual al gráfico
sel_order = left_series + right_series

# mapa nombre -> color (según trace)
name_to_color = {}
for tr in fig.data:
    nm = getattr(tr, "name", None)
    col = getattr(getattr(tr, "line", None), "color", None)
    if nm:
        name_to_color[nm] = col

TIP_MOM = "Variación del último dato mensual vs el mes previo (siempre fin de mes)."
TIP_YOY = "Variación del último dato mensual vs el mismo mes de hace 12 meses."
TIP_PER = "Variación entre el primer y el último dato del rango visible (respetando la frecuencia elegida)."

for name in sel_order:
    # si la serie está en el eje derecho, el trace se llama “<name> [eje derecho]”
    color = name_to_color.get(name, name_to_color.get(f"{name} [eje derecho]", "#3B82F6"))

    serie_full = (
        df[df["descripcion"]==name]
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
        title=name + (" [eje derecho]" if name in right_series else ""),
        color=color,
        mom=mom, yoy=yoy, d_per=d_per,
        tip_mom=TIP_MOM, tip_yoy=TIP_YOY, tip_per=TIP_PER,
    )
