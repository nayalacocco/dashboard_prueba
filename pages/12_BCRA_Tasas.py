# pages/12_BCRA_Tasas.py
import streamlit as st
import plotly.express as px
import pandas as pd

from ui import inject_css, range_controls, kpi
from bcra_utils import load_bcra_long, find_first, resample_series, compute_kpis

st.set_page_config(page_title="BCRA – Política monetaria y tasas", layout="wide")
inject_css()

st.title("🟦 Política monetaria y tasas")

# Cargamos catálogo long
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Corré el fetch (GitHub Actions) primero.")
    st.stop()

vars_all = sorted(df["descripcion"].dropna().unique().tolist())

# Intentamos detectar algunas tasas “claves”
tpm    = find_first(vars_all, "tasa", "política") or find_first(vars_all, "tasa", "de política")
pases  = find_first(vars_all, "tasa", "pases") or find_first(vars_all, "pase")  # por si el texto varía
badlar = find_first(vars_all, "badlar")
pfijo  = find_first(vars_all, "plazo", "fijo")

opciones = vars_all  # podés filtrar por la palabra 'tasa' si preferís

# --- DEFAULTS robustos: solo los que EXISTEN en opciones y no son None
predef = [tpm, badlar, pfijo, pases]
predef = [x for x in predef if x and x in opciones][:3]

# Multiselect sin romper si no hay predef
sel = st.multiselect(
    "Elegí 1–3 tasas",
    opciones,
    default=predef if predef else None,
    max_selections=3,
    help="Seleccioná hasta 3 series de tasas para comparar.",
    key="tasas_sel",
)

if not sel:
    st.info("Elegí al menos una tasa para comenzar.")
    st.stop()

# Armamos pivot
wfull = (
    df[df["descripcion"].isin(sel)]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

dmin, dmax = wfull.index.min(), wfull.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="tasas")
freq = "D" if freq_label.startswith("Diaria") else "M"

w = wfull.loc[d_ini:d_fin]
if freq == "M":
    w = w.resample("M").last()

w = w.dropna(how="all")
if w.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# Gráfico
fig = px.line(w.reset_index(), x="fecha", y=sel, labels={"fecha": "Fecha", "value": "Tasa (%)"})
fig.update_layout(
    template="plotly_dark", height=620, margin=dict(t=50, b=80, l=60, r=60),
    legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    title="Evolución de tasas seleccionadas",
)
fig.update_xaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
fig.update_yaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
st.plotly_chart(fig, use_container_width=True)

# KPIs para la PRIMERA serie seleccionada (a modo de síntesis)
principal = sel[0]
serie_full = (
    df[df["descripcion"] == principal]
    .set_index("fecha")["valor"]
    .sort_index()
    .astype(float)
)
serie_vis = w[principal].astype(float)

mom, yoy, d_per = compute_kpis(serie_full, serie_vis, d_fin)
fmt = lambda x: ("—" if x is None or pd.isna(x) else f"{x:,.2f}%")

c1, c2, c3 = st.columns(3)
with c1:
    kpi("Mensual (MoM)", fmt(mom),
        help_text="Variación mensual del último dato respecto al mes previo (siempre fin de mes).")
with c2:
    kpi("Interanual (YoY)", fmt(yoy),
        help_text="Variación interanual del último dato mensual (si hay historia suficiente).")
with c3:
    kpi("Δ en el período", fmt(d_per),
        help_text="Variación entre el primer y último dato del rango visible (diaria o mensual según el gráfico).")
