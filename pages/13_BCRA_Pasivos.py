import streamlit as st
import plotly.express as px
from ui import inject_css
from bcra_utils import load_bcra_long, find_first

st.set_page_config(page_title="BCRA – Pasivos remunerados", layout="wide")
inject_css()

st.title("🟦 Pasivos remunerados y absorción")

df = load_bcra_long()
vars_all = sorted(df["descripcion"].unique().tolist())

pasivos = find_first(vars_all, "pasivos", "remunerados") or find_first(vars_all, "leliq", "pases")
base    = find_first(vars_all, "base", "monetaria")

if not pasivos or not base:
    st.warning("No pude identificar las series de Pasivos remunerados o Base monetaria en el catálogo.")
    st.stop()

w = df[df["descripcion"].isin([pasivos, base])].pivot(index="fecha", columns="descripcion", values="valor").sort_index().dropna()
if w.empty:
    st.warning("No hay datos para calcular la relación.")
    st.stop()

fig1 = px.line(w.reset_index(), x="fecha", y=[pasivos, base], labels={"value":"Valor","fecha":"Fecha"})
fig1.update_layout(height=600, margin=dict(t=50,b=80,l=60,r=60),
                   legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
                   title="Stock (nivel)")
fig1.update_xaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
fig1.update_yaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
st.plotly_chart(fig1, use_container_width=True)

ratio = (w[pasivos] / w[base]).rename("Pasivos/Base").dropna()
fig2 = px.line(ratio.reset_index(), x="fecha", y="Pasivos/Base", title="Ratio Pasivos remunerados / Base monetaria")
fig2.update_layout(height=500, margin=dict(t=50,b=80,l=60,r=60))
fig2.update_xaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
fig2.update_yaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
st.plotly_chart(fig2, use_container_width=True)
