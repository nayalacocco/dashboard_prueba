# pages/11_BCRA_Agregados.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import re

from ui import inject_css, range_controls, kpi_triplet
from bcra_utils import load_bcra_long, resample_series, compute_kpis

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
    r"%|\bvar\.\b|\bvariaci[óo]n\b|\bpromedio\b|\bm[óo]vil\b|\bi\.a\.\b|\bYoY\b|\bMoM\b",
    r"\busd\b|\bd[oó]lar(es)?\b|\btipo\s+de\s+cambio\b|\breservas\b",
    r"\bdep[oó]sitos\b|\bpr[ée]stamos\b",
]
inc_re = re.compile("|".join(INCLUDE_PATTERNS), re.IGNORECASE)
exc_re = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)

candidatas = sorted(
    s for s in df["descripcion"].unique()
    if inc_re.search(s) and not exc_re.search(s)
)

# Fallback por si los nombres no matchean
if not candidatas:
    posibles = [
        "Base monetaria - Total (en millones de pesos)",
        "M1 Privado",
        "M2 Privado",
        "M3 Privado",
        "Circulación monetaria",
        "M2 Transaccional del Sector Privado - miles de millones de $",
    ]
    in_df = set(df["descripcion"].unique())
    candidatas = [s for s in posibles if s in in_df]
    if not candidatas:
        st.warning("No pude identificar agregados monetarios por nombre. Muestro toda la lista disponible.")
        candidatas = sorted(in_df)

# -----------------------------
# Selector de serie principal
# -----------------------------
var = st.selectbox("Serie principal", candidatas, index=0, help="Solo agregados monetarios en niveles.")

# Serie completa (historia total)
serie_full = (
    df[df["descripcion"] == var]
    .set_index("fecha")["valor"]
    .sort_index()
    .astype(float)
)
if serie_full.empty:
    st.warning("La serie seleccionada no tiene datos.")
    st.stop()

# ----------------------------------------
# Controles de rango + frecuencia (misma UI que Tasas)
# ----------------------------------------
dmin, dmax = serie_full.index.min(), serie_full.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="agregados")
freq = "D" if freq_label.startswith("Diaria") else "M"

# Serie visible
serie_vis = resample_series(serie_full.loc[d_ini:d_fin], freq=freq, how="last").dropna()
if serie_vis.empty:
    st.warning("El rango/frecuencia seleccionados dejan la serie sin datos.")
    st.stop()

# -----------------------------
# Gráfico (homogéneo con Tasas)
# -----------------------------
fig = go.Figure()

color = "#34D399"  # verde de la paleta
fig.add_trace(
    go.Scatter(
        x=serie_vis.index, y=serie_vis.values, mode="lines",
        name=var, line=dict(width=2, color=color),
        hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    )
)

fig.update_layout(
    template="atlas_dark",
    height=600,
    margin=dict(t=30, b=90, l=70, r=90),
    showlegend=False,   # como en Tasas, sin leyenda nativa
    uirevision=None,    # para que el encuadre siempre se recalculé
)
fig.update_xaxes(
    title_text="Fecha",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
)
fig.update_yaxes(
    title_text=var,
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
    showgrid=True, gridcolor="#1F2937",
    autorange=True, tickmode="auto", tickformat="~s", zeroline=False,
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# KPIs (tripleta como en Tasas)
# -----------------------------
mom, yoy, d_per = compute_kpis(serie_full, serie_vis)
kpi_triplet(
    title=var,
    color=color,
    mom=mom, yoy=yoy, d_per=d_per,
    tip_mom="Variación del último dato mensual vs el mes previo (fin de mes).",
    tip_yoy="Variación del último dato mensual vs el mismo mes de hace 12 meses.",
    tip_per="Variación entre primer y último dato del rango visible (frecuencia elegida).",
)
