# pages/13_BCRA_Pasivos.py
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import inject_css, range_controls, kpi_triplet
from bcra_utils import (
    load_bcra_long,
    resample_series,
    compute_kpis,
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

# Fallbacks
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
# Multi-selección hasta 3 (default: 2 series típicas)
# -----------------------------
default_sel = []
if pasivos_cands:
    default_sel.append(pasivos_cands[0])
if base_cands:
    default_sel.append(base_cands[0])

sel = st.multiselect(
    "Elegí hasta 3 series",
    sorted(set(pasivos_cands + base_cands)),
    default=default_sel,
    max_selections=3,
    help="Podés combinar pasivos (niveles) con base monetaria u otros agregados. Si mezclás % con niveles, se usa doble eje.",
    key="pasivos_sel",
)
if not sel:
    st.info("Elegí al menos una serie para comenzar.")
    st.stop()

# Wide (completo) para lo seleccionado
wfull = (
    df[df["descripcion"].isin(sel)]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

# -----------------------------
# Rango + Frecuencia (última acción gana)
# -----------------------------
dmin, dmax = wfull.index.min(), wfull.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="pasivos")
freq = "D" if freq_label.startswith("Diaria") else "M"

w = wfull.loc[d_ini:d_fin]
if freq == "M":
    w = w.resample("M").last()
w = w.dropna(how="all")
if w.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# =========================
# Heurística ejes (misma que Tasas/Agregados)
# =========================
def is_percent_name(name: str) -> bool:
    s = name.lower()
    tokens = ["%", "en %", "tna", "tea", "variación", "variacion", "yoy", "mom", "interanual", "mensual"]
    return any(t in s for t in tokens)

left_series  = [n for n in sel if is_percent_name(n)]
right_series = [n for n in sel if n not in left_series]
if not left_series:
    left_series = sel[:]
    right_series = []

# =========================
# Figura homogénea
# =========================
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

legend_left  = []
legend_right = []

# trazas izquierda
for i, name in enumerate(left_series):
    s = w[name].dropna()
    if s.empty: 
        continue
    color = palette[i % len(palette)]
    legend_left.append((name, color))
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=name, line=dict(width=2, color=color),
            yaxis="y",
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

# trazas derecha
for j, name in enumerate(right_series):
    s = w[name].dropna()
    if s.empty:
        continue
    color = palette[(len(left_series) + j) % len(palette)]
    legend_right.append((f"{name} [eje derecho]", color))
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=f"{name} [eje derecho]",
            line=dict(width=2, color=color),
            yaxis="y2",
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

fig.update_layout(
    template="atlas_dark",
    height=620,
    margin=dict(t=30, b=120, l=70, r=90),
    showlegend=False,
    uirevision=None,
)
fig.update_xaxes(title_text="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")

left_is_percent = any(is_percent_name(n) for n in left_series) if left_series else False
fig.update_yaxes(
    title_text="Eje izq",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
    showgrid=True, gridcolor="#1F2937",
    autorange=True, tickmode="auto",
    tickformat=(".0f" if left_is_percent else "~s"),
    zeroline=False,
)
if right_series:
    fig.update_layout(
        yaxis2=dict(
            title="Eje der",
            overlaying="y", side="right",
            showline=True, linewidth=1, linecolor="#E5E7EB",
            showgrid=False, autorange=True, tickmode="auto",
            tickformat="~s", zeroline=False,
        )
    )

# --- Escala logarítmica por eje ---
lc1, lc2, _ = st.columns([1,1,2])
with lc1:
    log_left = st.toggle("Escala log (eje izq)", value=False, key="log_left_pasivos")
with lc2:
    log_right = st.toggle("Escala log (eje der)", value=False, key="log_right_pasivos", disabled=(len(right_series)==0))

if log_left:
    fig.update_yaxes(type="log")
if log_right and right_series:
    fig.update_layout(yaxis2=dict(type="log"))

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Leyenda custom
# -----------------------------
if legend_left or legend_right:
    rows_html = []
    if legend_left:
        lt = "".join(f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>'
                     for lbl, c in legend_left)
        rows_html.append(f'<div class="col"><div class="hdr">Eje izquierdo</div>{lt}</div>')
    if legend_right:
        rt = "".join(f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>'
                     for lbl, c in legend_right)
        rows_html.append(f'<div class="col right"><div class="hdr">Eje derecho</div>{rt}</div>')

    legend_html = f"""
    <style>
      .split-legend {{
        display:flex; flex-wrap:wrap; gap:24px; justify-content:space-between;
        margin-top:-8px; margin-bottom:10px;
      }}
      .split-legend .col {{ flex:1 1 380px; }}
      .split-legend .col.right {{ text-align:right; }}
      .split-legend .hdr {{ color:#9CA3AF; font-size:.9rem; margin-bottom:6px; }}
      .split-legend .li {{ color:#E5E7EB; font-size:.95rem; margin:4px 0; display:flex; align-items:center; gap:8px; }}
      .split-legend .col.right .li {{ justify-content:flex-end; }}
      .split-legend .dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
    </style>
    <div class="split-legend">{''.join(rows_html)}</div>
    """
    st.markdown(legend_html, unsafe_allow_html=True)

# -----------------------------
# KPI tripletas por serie (como en las otras páginas)
# -----------------------------
def kpis_for(name: str, color: str):
    serie_full = (
        df[df["descripcion"] == name]
        .set_index("fecha")["valor"]
        .sort_index()
        .astype(float)
    )
    serie_visible = resample_series(
        wfull[name].loc[d_ini:d_fin].dropna(),
        freq=("D" if freq_label.startswith("Diaria") else "M"),
        how="last",
    ).dropna()

    mom, yoy, d_per = compute_kpis(serie_full, serie_visible)
    kpi_triplet(
        title=name, color=color,
        mom=mom, yoy=yoy, d_per=d_per,
        tip_mom="Variación del último dato mensual vs el mes previo (fin de mes).",
        tip_yoy="Variación del último dato mensual vs el mismo mes de hace 12 meses.",
        tip_per="Variación entre primer y último dato del rango visible (frecuencia elegida).",
    )

palette_cycle = ["#60A5FA", "#F87171", "#34D399"]
for idx, name in enumerate(sel):
    kpis_for(name, palette_cycle[idx % len(palette_cycle)])

# -----------------------------
# Ratio Pasivos/Base (si hay una de cada grupo)
#   - Si hay múltiples pasivos y múltiples bases, usa el primer pasivo y la primera base seleccionados.
# -----------------------------
def is_pasivo(name: str) -> bool:
    return bool(PASIVOS_INC.search(name) and not PASIVOS_EXC.search(name))

def is_base(name: str) -> bool:
    return bool(BASE_INC.search(name))

pasivo_pick = next((n for n in sel if is_pasivo(n)), None)
base_pick   = next((n for n in sel if is_base(n)), None)

if pasivo_pick and base_pick:
    ratio = (w[pasivo_pick] / w[base_pick]).rename("Pasivos/Base").dropna()
    if not ratio.empty:
        ratio_fig = go.Figure()
        ratio_fig.add_trace(
            go.Scatter(
                x=ratio.index, y=ratio.values, mode="lines",
                name="Pasivos/Base", line=dict(width=2, color="#A78BFA"),  # violeta
            )
        )
        ratio_fig.update_layout(
            template="atlas_dark",
            height=500,
            margin=dict(t=30, b=70, l=70, r=70),
            title=f"Ratio {pasivo_pick} / {base_pick}",
            showlegend=False,
        )
        ratio_fig.update_xaxes(title_text="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
        ratio_fig.update_yaxes(title_text="Ratio",  showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
        st.plotly_chart(ratio_fig, use_container_width=True)
