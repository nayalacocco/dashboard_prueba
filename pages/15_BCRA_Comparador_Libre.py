import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date
from bcra_utils import load_bcra_long, resample_series, nice_ticks, aligned_right_ticks_round
from ui import inject_css
inject_css()

st.set_page_config(page_title="BCRA – Comparador libre", layout="wide")
st.title("🟦 Comparador libre")

df = load_bcra_long()
vars_all = sorted(df["descripcion"].unique().tolist())

sel = st.multiselect("Elegí 1 o 2 variables", options=vars_all, default=[vars_all[0]], max_selections=2)
if not sel:
    st.stop()

df_sel = df[df["descripcion"].isin(sel)]
fmin, fmax = df_sel["fecha"].min().date(), df_sel["fecha"].max().date()

preset = st.radio("Rango", ["12m","24m","Máximo"], horizontal=True, index=0)
if preset=="12m":
    from dateutil.relativedelta import relativedelta
    d_ini, d_fin = fmax - relativedelta(months=12), fmax
elif preset=="24m":
    from dateutil.relativedelta import relativedelta
    d_ini, d_fin = fmax - relativedelta(months=24), fmax
else:
    d_ini, d_fin = fmin, fmax

freq = st.selectbox("Frecuencia", ["Diaria","Mensual (fin de mes)"], index=1)

mask = (df_sel["fecha"]>=pd.to_datetime(d_ini)) & (df_sel["fecha"]<=pd.to_datetime(d_fin))
w = df_sel.loc[mask].pivot(index="fecha", columns="descripcion", values="valor").sort_index()
if w.empty:
    st.info("Sin datos en el rango.")
    st.stop()

if freq.startswith("Mensual"):
    w = w.resample("M").last()

if len(sel) == 1:
    fig = px.line(w.reset_index(), x="fecha", y=sel[0], title=sel[0], labels={"fecha":"Fecha","value":"Valor"})
    fig.update_layout(height=620, margin=dict(t=50,b=80), legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"))
    st.plotly_chart(fig, use_container_width=True)
else:
    v1, v2 = sel
    s1, s2 = w[v1].dropna(), w[v2].dropna()
    if s1.empty or s2.empty:
        st.info("Alguna serie está vacía en el rango.")
        st.stop()
    fig = go.Figure()
    fig.add_scatter(x=s1.index, y=s1.values, name=v1, mode="lines", yaxis="y1")
    fig.add_scatter(x=s2.index, y=s2.values, name=v2, mode="lines", yaxis="y2")

    # grilla izquierda y ticks redondos alineados a la izquierda en el eje derecho
    lmin, lmax = float(s1.min()), float(s1.max())
    left_ticks = nice_ticks(lmin, lmax, max_ticks=7)
    fig.update_yaxes(title=v1, tickmode="array", tickvals=left_ticks, showgrid=True, side="left", overlaying=None)

    rmin, rmax = float(s2.min()), float(s2.max())
    right_ticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)
    fig.update_yaxes(title=v2, tickmode="array", tickvals=right_ticks, showgrid=False, side="right", overlaying="y", range=[r0, r1])

    fig.update_layout(
        title=f"{v1} vs {v2}",
        xaxis_title="Fecha",
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
        height=620, margin=dict(t=50,b=80)
    )
    st.plotly_chart(fig, use_container_width=True)
