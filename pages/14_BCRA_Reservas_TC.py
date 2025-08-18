import streamlit as st
import plotly.graph_objects as go
import numpy as np
from ui import inject_css, range_controls
from bcra_utils import load_bcra_long, find_first, nice_ticks, aligned_right_ticks_round

st.set_page_config(page_title="BCRA – Reservas y TC", layout="wide")
inject_css()

st.title("🟦 Reservas y tipo de cambio")

df = load_bcra_long()
vars_all = sorted(df["descripcion"].unique().tolist())

reservas = find_first(vars_all, "reservas", "internacionales") or find_first(vars_all, "saldo", "reservas")
tc_a3500 = find_first(vars_all, "tipo de cambio", "3500") or find_first(vars_all, "com.", "a", "3500")
base     = find_first(vars_all, "base", "monetaria")

if not reservas or not tc_a3500:
    st.warning("No pude identificar reservas y/o tipo de cambio en el catálogo.")
    st.stop()

wfull = df[df["descripcion"].isin([reservas, tc_a3500] + ([base] if base else []))].pivot(index="fecha", columns="descripcion", values="valor").sort_index()
dmin, dmax = wfull.index.min(), wfull.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="reservas")
w = wfull.loc[d_ini:d_fin]
if freq_label.startswith("Mensual"):
    w = w.resample("M").last()

s1 = w[reservas].dropna()
s2 = w[tc_a3500].dropna()

fig = go.Figure()
fig.update_layout(template="plotly_dark")
fig.add_scatter(x=s1.index, y=s1.values, name=reservas, mode="lines", yaxis="y1")
fig.add_scatter(x=s2.index, y=s2.values, name=tc_a3500, mode="lines", yaxis="y2")

lmin, lmax = float(np.nanmin(s1)), float(np.nanmax(s1))
left_ticks = nice_ticks(lmin, lmax, max_ticks=7)
fig.update_yaxes(title=reservas, tickmode="array", tickvals=left_ticks, showgrid=True, side="left", overlaying=None)

rmin, rmax = float(np.nanmin(s2)), float(np.nanmax(s2))
right_ticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)
fig.update_yaxes(title=tc_a3500, tickmode="array", tickvals=right_ticks, showgrid=False, side="right", overlaying="y", range=[r0, r1], tickformat=".2s")

fig.update_layout(
    title="Reservas (USD) vs Tipo de cambio oficial (A3500)",
    xaxis=dict(title="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside"),
    legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    height=600, margin=dict(t=50,b=80,l=60,r=60)
)
st.plotly_chart(fig, use_container_width=True)
