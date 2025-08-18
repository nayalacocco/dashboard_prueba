import streamlit as st
import plotly.express as px
from ui import inject_css, range_controls
from bcra_utils import load_bcra_long, find_first

st.set_page_config(page_title="BCRA – Tasas", layout="wide")
inject_css()

st.title("🟦 Política monetaria y tasas")

df = load_bcra_long()
vars_all = sorted(df["descripcion"].unique().tolist())

tpm   = find_first(vars_all, "tasa", "politica") or find_first(vars_all, "tna", "politica")
pases = find_first(vars_all, "pases") or find_first(vars_all, "pase", "pasivo")
badlar= find_first(vars_all, "badlar", "privados")
pfijo = find_first(vars_all, "plazo", "fijo")

opciones = [v for v in [tpm, pases, badlar, pfijo] if v]
sel = st.multiselect("Elegí 1–3 tasas", opciones, default=[tpm, badlar], max_selections=3)

if sel:
    wfull = df[df["descripcion"].isin(sel)].pivot(index="fecha", columns="descripcion", values="valor").sort_index()
    dmin, dmax = wfull.index.min(), wfull.index.max()
    d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="tasas")
    w = wfull.loc[d_ini:d_fin]
    if freq_label.startswith("Mensual"):
        w = w.resample("M").mean()

    fig = px.line(w.reset_index(), x="fecha", y=sel, labels={"value":"% TNA","fecha":"Fecha","variable":"Tasa"})
    fig.update_layout(template="plotly_dark", height=600, margin=dict(t=50,b=80,l=60,r=60),
                      legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"))
    fig.update_xaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
    fig.update_yaxes(showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
    st.plotly_chart(fig, use_container_width=True)
