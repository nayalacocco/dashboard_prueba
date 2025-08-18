# pages/11_BCRA_Agregados.py
import streamlit as st
import plotly.express as px
import pandas as pd

from ui import inject_css, kpi, range_controls
from bcra_utils import (
    load_bcra_long,
    find_first,
    resample_series,
    compute_kpis,   # KPIs robustos (MoM/YoY con mensual fin de mes + Δ en período visible)
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

vars_all = sorted(df["descripcion"].dropna().unique().tolist())

# Preselecciones “inteligentes” (si no existen, se omiten)
base = find_first(vars_all, "base", "monetaria")
m1   = find_first(vars_all, "m1")
m2   = find_first(vars_all, "m2", "privado")
m3   = find_first(vars_all, "m3", "privado")
circ = find_first(vars_all, "circulacion", "monetaria")

opciones = [v for v in [base, m1, m2, m3, circ] if v] or vars_all

# -----------------------------
# Selector de serie principal
# -----------------------------
var = st.selectbox("Serie principal", opciones, index=0, help="Elegí qué agregado ver")

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
# KPIs (una sola vez, robustos)
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
