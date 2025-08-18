import streamlit as st
import plotly.express as px
import pandas as pd
from ui import inject_css, kpi
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

colA, colB = st.columns([2,1])
with colA:
    var = st.selectbox("Serie principal", opciones, index=0)
with colB:
    freq = st.selectbox("Frecuencia", ["Diaria", "Mensual (fin de mes)"], index=1)

serie = df[df["descripcion"]==var].set_index("fecha")["valor"].sort_index()
serie = resample_series(serie, "D" if freq.startswith("Diaria") else "M", "last")

fig = px.line(serie.reset_index(), x="fecha", y="valor", title=var, labels={"fecha":"Fecha","valor":"Valor"})
fig.update_layout(height=600, margin=dict(t=50,b=80,l=60,r=60),
                  legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"))
fig.update_xaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
fig.update_yaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
st.plotly_chart(fig, use_container_width=True)

m = serie.resample("M").last()
col1, col2, col3 = st.columns(3)
mom = (m.pct_change(1).iloc[-1]*100) if len(m)>1 else None
yoy = (m.pct_change(12).iloc[-1]*100) if len(m)>12 else None
ytd = (m.iloc[-1]/m[m.index.year==m.index[-1].year].iloc[0]-1)*100 if (m.index.year==m.index[-1].year).sum()>0 else None
kpi("Mensual (MoM)", f"{mom:,.2f}%" if mom is not None else "—")
kpi("Interanual (YoY)", f"{yoy:,.2f}%" if yoy is not None else "—")
kpi("YTD", f"{ytd:,.2f}%" if ytd is not None else "—")

st.subheader("Comparador rápido de agregados")
comp = st.multiselect("Elegí hasta 3 agregados", opciones, default=[base, m2], max_selections=3)
if comp:
    dfw = df[df["descripcion"].isin(comp)].pivot(index="fecha", columns="descripcion", values="valor").sort_index()
    if not dfw.empty:
        if freq.startswith("Mensual"): dfw = dfw.resample("M").last()
        fig2 = px.line(dfw.reset_index(), x="fecha", y=comp, labels={"value":"Valor","fecha":"Fecha","variable":"Serie"})
        fig2.update_layout(height=600, margin=dict(t=50,b=80,l=60,r=60),
                           legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"))
        fig2.update_xaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
        fig2.update_yaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
        st.plotly_chart(fig2, use_container_width=True)
