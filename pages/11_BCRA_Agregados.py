# pages/11_BCRA_Agregados.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import re

from ui import inject_css, range_controls, kpi_triplet
from bcra_utils import (
    load_bcra_long,
    resample_series,
    compute_kpis,
)

st.set_page_config(page_title="BCRA – Agregados", layout="wide")
inject_css()
st.title("🟦 Agregados monetarios")

# -----------------------------
# Carga de datos (long format)
# -----------------------------
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Corré el fetch (GitHub Actions) primero.")
    st.stop()

df["descripcion"] = df["descripcion"].fillna("").astype(str)

# -----------------------------
# Catálogo curado: solo agregados monetarios (niveles)
# -----------------------------
INCLUDE_PATTERNS = [
    r"\bbase\s+monetaria\b",
    r"\bm1\b",
    r"\bm2\b",
    r"\bm3\b",
    r"\bcirculaci[óo]n\s+monetaria\b",
    r"\bcirculante\b",
    r"\bm2\s+transaccional\b",
]
EXCLUDE_PATTERNS = [
    r"\btasa\b|\binter[eé]s\b|\bbadlar\b|\bpases?\b|\bleliq\b|\bplazo\s+fijo\b",
    r"%|\bvar\.\b|\bvariaci[óo]n\b|\bpromedio\b|\bm[óo]vil\b|\bi\.a\.\b|\byoy\b|\bmom\b",
    r"\busd\b|\bd[oó]lar(es)?\b|\btipo\s+de\s+cambio\b|\breservas\b",
    r"\bdep[oó]sitos\b|\bpr[ée]stamos\b",
]

inc_re = re.compile("|".join(INCLUDE_PATTERNS), re.IGNORECASE)
exc_re = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)

candidatas = sorted(
    s for s in df["descripcion"].unique()
    if inc_re.search(s) and not exc_re.search(s)
)

# Fallback sensato
if not candidatas:
    posibles = [
        "Base monetaria - Total (en millones de pesos)",
        "M1 Privado",
        "M2 Privado",
        "M3 Privado",
        "Circulación monetaria",
        "M2 Transaccional del Sector Privado - miles de millones de $",
    ]
    candidatas = [s for s in posibles if s in set(df["descripcion"].unique())]
    if not candidatas:
        st.warning("No pude identificar agregados por nombre. Muestro toda la lista disponible.")
        candidatas = sorted(df["descripcion"].unique().tolist())

# -----------------------------
# Multi-selección hasta 3
# -----------------------------
sel = st.multiselect(
    "Elegí hasta 3 series de agregados",
    candidatas,
    default=candidatas[:2] if candidatas else None,
    max_selections=3,
    help="Podés comparar hasta 3 agregados. Si mezclás porcentajes con niveles, se usa doble eje.",
    key="agregados_sel",
)
if not sel:
    st.info("Elegí al menos una serie para comenzar.")
    st.stop()

wide_full = (
    df[df["descripcion"].isin(sel)]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

# ----------------------------------------
# Controles de rango + frecuencia
# ----------------------------------------
dmin, dmax = wide_full.index.min(), wide_full.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="agregados")
freq = "D" if freq_label.startswith("Diaria") else "M"

wide_vis = wide_full.loc[d_ini:d_fin]
if freq == "M":
    wide_vis = wide_vis.resample("M").last()
wide_vis = wide_vis.dropna(how="all")
if wide_vis.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# =========================
# Heurística ejes (misma que Tasas)
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
# Figura (homogénea con Tasas)
# =========================
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

legend_left  = []
legend_right = []

for i, name in enumerate(left_series):
    s = wide_vis[name].dropna()
    if s.empty: continue
    color = palette[i % len(palette)]
    legend_left.append((name, color))
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=name, line=dict(width=2, color=color),
        yaxis="y", hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

for j, name in enumerate(right_series):
    s = wide_vis[name].dropna()
    if s.empty: continue
    color = palette[(len(left_series) + j) % len(palette)]
    legend_right.append((f"{name} [eje derecho]", color))
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=f"{name} [eje derecho]", line=dict(width=2, color=color),
        yaxis="y2", hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

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
log_col1, log_col2, _ = st.columns([1,1,2])
with log_col1:
    log_left = st.toggle("Escala log (eje izq)", value=False, key="log_left_agregados")
with log_col2:
    log_right = st.toggle("Escala log (eje der)", value=False, key="log_right_agregados", disabled=(len(right_series)==0))

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
# KPIs por serie (tripleta)
# -----------------------------
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
        title=name, color=color,
        mom=mom, yoy=yoy, d_per=d_per,
        tip_mom="Variación del último dato mensual vs el mes previo (fin de mes).",
        tip_yoy="Variación del último dato mensual vs el mismo mes de hace 12 meses.",
        tip_per="Variación entre primer y último dato del rango visible (frecuencia elegida).",
    )

palette_cycle = ["#60A5FA", "#F87171", "#34D399"]
for idx, name in enumerate(sel):
    kpis_for(name, palette_cycle[idx % len(palette_cycle)])
