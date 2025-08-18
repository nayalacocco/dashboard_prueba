# pages/14_BCRA_Reservas.py
import streamlit as st
import plotly.graph_objects as go
from ui import inject_css, range_controls
from bcra_utils import load_bcra_long, find_first

st.set_page_config(page_title="BCRA – Reservas y Tipo de Cambio", layout="wide")
inject_css()

st.title("🟦 Reservas y tipo de cambio")

# --- Datos
df = load_bcra_long()
vars_all = sorted(df["descripcion"].unique().tolist())

# identificar series
reservas = find_first(vars_all, "reservas")
tc = find_first(vars_all, "tipo de cambio mayorista") or find_first(vars_all, "a3500")

if not reservas or not tc:
    st.warning("No pude identificar series de Reservas o Tipo de cambio.")
    st.stop()

# pivot más ordenado
wide_all = (
    df[df["descripcion"].isin([reservas, tc])]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
    .dropna(how="all")
)

if wide_all.empty:
    st.warning("No hay datos para graficar.")
    st.stop()

# --- Controles
dmin, dmax = wide_all.index.min(), wide_all.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="reservas_tc")

serie_res = st.selectbox("Serie de reservas", [reservas], index=0)
serie_tc = st.selectbox("Serie de tipo de cambio", [tc], index=0)

# --- Filtrar y resamplear
df_sel = wide_all.loc[d_ini:d_fin, [serie_res, serie_tc]].dropna(how="all")

if freq_label.startswith("Mensual"):
    df_sel = df_sel.resample("M").last()

# --- Graficar con doble eje si escalas difieren mucho
fig = go.Figure()

y0 = df_sel[serie_res]
y1 = df_sel[serie_tc]

scale_ratio = (y0.max() / y0.min()) / max(1, (y1.max() / y1.min()))

fig.add_trace(go.Scatter(
    x=df_sel.index, y=y0, mode="lines",
    name=serie_res, yaxis="y1"
))

fig.add_trace(go.Scatter(
    x=df_sel.index, y=y1, mode="lines",
    name=serie_tc, yaxis="y2" if scale_ratio > 5 else "y1"
))

fig.update_layout(
    template="plotly_dark",
    height=600,
    margin=dict(t=50, b=80, l=60, r=60),
    legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    xaxis=dict(title="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside"),
    yaxis=dict(title="Reservas (USD)", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside"),
)

# si usamos doble eje
if scale_ratio > 5:
    fig.update_layout(
        yaxis2=dict(
            title="Tipo de cambio (ARS/USD)",
            overlaying="y",
            side="right",
            showline=True,
            linewidth=1,
            linecolor="#E5E7EB",
            ticks="outside",
        )
    )

st.plotly_chart(fig, use_container_width=True)
