# pages/11_BCRA_Agregados.py
import streamlit as st
import plotly.express as px
import pandas as pd

from ui import inject_css, kpi, range_controls
from bcra_utils import load_bcra_long, find_first, resample_series

st.set_page_config(page_title="BCRA – Agregados", layout="wide")
inject_css()

st.title("🟦 Agregados monetarios")

df = load_bcra_long()
vars_all = sorted(df["descripcion"].unique().tolist())

base = find_first(vars_all, "base", "monetaria")
m1   = find_first(vars_all, "m1")
m2   = find_first(vars_all, "m2", "privado")
m3   = find_first(vars_all, "m3", "privado")
circ = find_first(vars_all, "circulacion", "monetaria")
opciones = [v for v in [base, m1, m2, m3, circ] if v]

var = st.selectbox("Serie principal", opciones, index=0, help="Elegí qué agregado ver")

# serie completa (historia total)
serie_full = (
    df[df["descripcion"] == var]
    .set_index("fecha")["valor"]
    .sort_index()
    .astype(float)
)

# --- Controles de rango + frecuencia (default Diaria)
dmin, dmax = serie_full.index.min(), serie_full.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="agregados")

# serie visible según controles
freq = "D" if freq_label.startswith("Diaria") else "M"
serie_vis = resample_series(serie_full.loc[d_ini:d_fin], freq=freq, how="last").dropna()

# --- Gráfico
fig = px.line(
    serie_vis.reset_index(), x="fecha", y="valor",
    title=var, labels={"fecha": "Fecha", "valor": "Valor"}
)
fig.update_layout(
    template="plotly_dark", height=600, margin=dict(t=50, b=80, l=60, r=60),
    legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center")
)
fig.update_xaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
fig.update_yaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
st.plotly_chart(fig, use_container_width=True)

# =========================
#  KPIs con tooltips
# =========================

def pct_change_month_over_month(s: pd.Series) -> float | None:
    """MoM usando serie mensual del histórico, hasta el fin visible."""
    if s.empty:
        return None
    # tomamos fin de mes del histórico para robustez
    m = s.resample("M").last().dropna()
    if len(m) < 2:
        return None
    # último punto <= d_fin
    m = m.loc[:d_fin]
    if len(m) < 2:
        return None
    return (m.iloc[-1] / m.iloc[-2] - 1.0) * 100.0

def pct_change_yoy(s: pd.Series) -> float | None:
    """YoY contra el mismo mes (o punto) de hace 12 meses en el histórico completo."""
    if s.empty:
        return None
    m = s.resample("M").last().dropna()
    if m.empty:
        return None
    last_idx = m.index[m.index <= d_fin]
    if len(last_idx) == 0:
        return None
    last_idx = last_idx[-1]
    ref_date = last_idx - pd.DateOffset(years=1)
    hist = m.loc[:ref_date]
    if len(hist) == 0:
        return None
    base = hist.iloc[-1]
    if base == 0:
        return None
    return (m.loc[last_idx] / base - 1.0) * 100.0

def pct_change_visible_period(s_visible: pd.Series) -> float | None:
    """Δ en el período visible (primer vs último dato del gráfico, con frecuencia elegida)."""
    s = s_visible.dropna()
    if len(s) < 2:
        return None
    first, last = s.iloc[0], s.iloc[-1]
    if first == 0:
        return None
    return (last / first - 1.0) * 100.0

# calcular métricas
mom = pct_change_month_over_month(serie_full)
yoy = pct_change_yoy(serie_full)
d_per = pct_change_visible_period(serie_vis)

# formateo helper
fmt = lambda x: ("—" if x is None or pd.isna(x) else f"{x:,.2f}%")

# KPIs con tooltips (help)
col1, col2, col3 = st.columns(3)
with col1:
    kpi(
        "Mensual (MoM)",
        fmt(mom),
        help_text="Variación porcentual respecto al mes previo (calculada con serie mensual del histórico)."
    )
with col2:
    kpi(
        "Interanual (YoY)",
        fmt(yoy),
        help_text=(
            "Variación porcentual contra el mismo mes de hace 12 meses. "
            "Se calcula aunque el rango visible sea menor a 12 meses; "
            "si no hay dato hace un año, se muestra —."
        ),
    )
with col3:
    kpi(
        "Δ en el período",
        fmt(d_per),
        help_text=(
            "Variación porcentual entre el primer y el último dato del rango visible "
            "(respeta la frecuencia elegida: diaria o fin de mes)."
        ),
    )

from bcra_utils import compute_kpis
from ui import kpi

# ...

mom, yoy, d_per = compute_kpis(serie_full, serie_vis, d_fin)

fmt = lambda x: ("—" if x is None or pd.isna(x) else f"{x:,.2f}%")

c1, c2, c3 = st.columns(3)
with c1:
    kpi("Mensual (MoM)", fmt(mom),
        help_text="Variación porcentual del último dato mensual respecto al mes previo (siempre fin de mes).")
with c2:
    kpi("Interanual (YoY)", fmt(yoy),
        help_text=("Variación porcentual del último dato mensual respecto al mismo período de hace 12 meses. "
                   "Se muestra aunque el rango visible sea menor a 12 meses (si hay historia suficiente)."))
with c3:
    kpi("Δ en el período", fmt(d_per),
        help_text=("Variación porcentual entre el primer y el último dato del rango visible "
                   "(con la frecuencia actual del gráfico)."))
