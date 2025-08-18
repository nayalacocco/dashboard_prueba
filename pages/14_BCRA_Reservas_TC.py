import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from bcra_utils import load_bcra_long, find_first

st.set_page_config(page_title="BCRA – Reservas y TC", layout="wide")
st.title("🟦 Reservas y tipo de cambio")

df = load_bcra_long()
vars_all = sorted(df["descripcion"].unique().tolist())

reservas = find_first(vars_all, "reservas", "internacionales") or find_first(vars_all, "saldo", "reservas")
tc_a3500 = find_first(vars_all, "tipo de cambio", "3500") or find_first(vars_all, "com.", "a", "3500")
base     = find_first(vars_all, "base", "monetaria")

opts = [v for v in [reservas, tc_a3500] if v]
if len(opts) < 2:
    st.warning("No pude identificar reservas y/o tipo de cambio en el catálogo.")
    st.stop()

w = df[df["descripcion"].isin(opts + ([base] if base else []))].pivot(index="fecha", columns="descripcion", values="valor").sort_index().dropna(how="all")
if w.empty:
    st.warning("Sin datos para graficar.")
    st.stop()

# Doble eje: Reservas (izq) vs TC (der)
left, right = reservas, tc_a3500
fig = go.Figure()
fig.add_scatter(x=w.index, y=w[left], name=left, mode="lines", yaxis="y1")
fig.add_scatter(x=w.index, y=w[right], name=right, mode="lines", yaxis="y2")
fig.update_layout(
    title="Reservas (USD) vs Tipo de cambio oficial (A3500)",
    xaxis=dict(title="Fecha"),
    yaxis=dict(title=left),
    yaxis2=dict(title=right, overlaying="y", side="right"),
    legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
    height=600, margin=dict(t=50,b=80)
)
st.plotly_chart(fig, use_container_width=True)

# Ratio Reservas/Base (si está disponible)
if base and base in w.columns:
    # ojo: unidades distintas → ratio es sólo un indicador (escala relativa)
    ratio = (w[reservas] / w[base]).dropna().rename("Reservas/Base")
    if not ratio.empty:
        fig2 = px.line(ratio.reset_index(), x="fecha", y="Reservas/Base", title="Reservas / Base monetaria (indicador de respaldo)")
        fig2.update_layout(height=500, margin=dict(t=50,b=60))
        st.plotly_chart(fig2, use_container_width=True)
