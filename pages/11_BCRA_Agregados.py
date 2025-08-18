# pages/11_BCRA_Agregados.py
import streamlit as st
import plotly.express as px
import pandas as pd
import re

from ui import inject_css, kpi, range_controls
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

# Normalizo descripciones
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

# Excluir tasas, variaciones/porcentajes, dólar/reservas y otros no-aggregados
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

# Fallback sensato si por naming no matchean los regex
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
        st.warning("No pude identificar agregados monetarios por nombre. Muestro toda la lista disponible.")
        candidatas = sorted(df["descripcion"].unique().tolist())

# -----------------------------
# Selector de serie principal (curado)
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
# Controles de rango + frecuencia (UI)
# ----------------------------------------
dmin, dmax = serie_full.index.min(), serie_full.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="agregados")
freq = "D" if freq_label.startswith("Diaria") else "M"

# Serie visible según controles
serie_vis = resample_series(serie_full.loc[d_ini:d_fin], freq=freq, how="last").dropna()
if serie_vis.empty:
    st.warning("El rango/frecuencia seleccionados dejan la serie sin datos.")
    st.stop()

# -----------------------------
# Gráfico principal
# -----------------------------
fig = px.line(
    serie_vis.reset_index(), x="fecha", y="valor",
    title=var, labels={"fecha": "Fecha", "valor": "Valor"}
)
fig.update_layout(
    template="plotly_dark",
    height=600,
    margin=dict(t=50, b=80, l=60, r=60),
    legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
)
fig.update_xaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
fig.update_yaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# KPIs (MoM / YoY / Δ período)
# -----------------------------
mom, yoy, d_per = compute_kpis(serie_full, serie_vis)

fmt = lambda x: ("—" if x is None or pd.isna(x) else f"{x:,.2f}%")

c1, c2, c3 = st.columns(3)
with c1:
    kpi(
        "Mensual (MoM)",
        fmt(mom),
        help_text="Variación del último dato mensual vs el mes previo (siempre fin de mes, consistente con lo visible).",
    )
with c2:
    kpi(
        "Interanual (YoY)",
        fmt(yoy),
        help_text="Variación del último dato mensual vs el mismo mes de hace 12 meses (si hay historia suficiente).",
    )
with c3:
    kpi(
        "Δ en el período",
        fmt(d_per),
        help_text="Variación entre el primer y el último dato del rango visible (respetando la frecuencia elegida).",
    )
