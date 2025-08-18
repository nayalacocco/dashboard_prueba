import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import date
from bcra_utils import load_bcra_long, find_first, resample_series, yoy_monthly_from_daily

st.set_page_config(page_title="BCRA – Agregados", layout="wide")
st.title("🟦 Agregados monetarios")

df = load_bcra_long()
vars_all = sorted(df["descripcion"].unique().tolist())

# Sugerencias por nombre (ajustá si las descripciones reales difieren)
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
fig.update_layout(height=600, margin=dict(t=50,b=60))
st.plotly_chart(fig, use_container_width=True)

# Crecimientos
st.subheader("Crecimientos")
m = serie.resample("M").last()
col1, col2, col3 = st.columns(3)
with col1:
    mom = m.pct_change(1).iloc[-1]*100 if len(m)>1 else None
    st.metric("Mensual (MoM)", f"{mom:,.2f}%" if mom is not None else "—")
with col2:
    yoy = m.pct_change(12).iloc[-1]*100 if len(m)>12 else None
    st.metric("Interanual (YoY)", f"{yoy:,.2f}%" if yoy is not None else "—")
with col3:
    ytd = (m.iloc[-1]/m[m.index.year==m.index[-1].year].iloc[0]-1)*100 if (m.index.year==m.index[-1].year).sum()>0 else None
    st.metric("YTD", f"{ytd:,.2f}%" if ytd is not None else "—")

# Comparador corto entre agregados
st.subheader("Comparador rápido de agregados")
comp = st.multiselect("Elegí hasta 3 agregados", opciones, default=[base, m2], max_selections=3)
if comp:
    dfw = df[df["descripcion"].isin(comp)].pivot(index="fecha", columns="descripcion", values="valor").sort_index()
    if not dfw.empty:
        if freq.startswith("Mensual"):
            dfw = dfw.resample("M").last()
        fig2 = px.line(dfw.reset_index(), x="fecha", y=comp, labels={"value":"Valor","fecha":"Fecha","variable":"Serie"})
        fig2.update_layout(height=600, margin=dict(t=50,b=60), legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"))
        st.plotly_chart(fig2, use_container_width=True)
