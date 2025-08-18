# pages/15_BCRA_Comparador_Libre.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from ui import inject_css, range_controls
from bcra_utils import (
    load_bcra_long,
    find_first,
    resample_series,
    nice_ticks,
    aligned_right_ticks_round,
)

st.set_page_config(page_title="BCRA – Comparador libre", layout="wide")
inject_css()

st.title("🧪 Comparador libre")
st.caption("Elegí hasta dos series del BCRA y comparalas en distintos modos. "
           "Podés filtrar por rango rápido, gobierno y cambiar la frecuencia (diaria/mensual).")

# ---------------------------------------------------------------------
# Carga y selección de variables
# ---------------------------------------------------------------------
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Asegurate de correr el fetch en GitHub Actions.")
    st.stop()

vars_all = sorted(df["descripcion"].dropna().unique().tolist())

# defaults amigables si existen
base_default = find_first(vars_all, "base", "monetaria")
reservas_default = find_first(vars_all, "reservas", "internacionales") or find_first(vars_all, "saldo", "reservas")

col_sel = st.columns([1.2, 1])
with col_sel[0]:
    selected = st.multiselect(
        "Seleccioná 1 o 2 variables",
        vars_all,
        default=[v for v in [base_default, reservas_default] if v][:2],
        max_selections=2,
    )

with col_sel[1]:
    modo = st.radio(
        "Modo de comparación",
        ("Mismo eje", "Doble eje Y", "Base 100"),
        index=1,
        help="Mismo eje: ambas series comparten escala. Doble eje Y: escalas separadas con grillas alineadas. "
             "Base 100: ambas series reescaladas a 100 en el primer dato del rango.",
    )

if not selected:
    st.info("Elegí al menos una variable para comenzar.")
    st.stop()

wfull = df[df["descripcion"].isin(selected)].pivot(
    index="fecha", columns="descripcion", values="valor"
).sort_index()

if wfull.empty:
    st.warning("No hay datos para graficar con la selección actual.")
    st.stop()

# ---------------------------------------------------------------------
# Controles de rango / frecuencia (DIARIA por defecto)
# ---------------------------------------------------------------------
dmin, dmax = wfull.index.min(), wfull.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="comparador")

w = wfull.loc[d_ini:d_fin]
freq = "D" if freq_label.startswith("Diaria") else "M"

if freq == "M":
    # para mensual usamos fin de mes (como en otros módulos)
    w = w.resample("M").last()

# limpiar todo NaN
w = w.dropna(how="all")
if w.empty:
    st.warning("El rango/frecuencia seleccionados dejan la serie sin datos.")
    st.stop()

# ---------------------------------------------------------------------
# Construcción del gráfico según modo
# ---------------------------------------------------------------------
fig = go.Figure()
fig.update_layout(template="plotly_dark")
colors = ["#60A5FA", "#22D3EE"]  # azul y cian

if modo == "Base 100":
    # Reescala cada serie a 100 en el primer dato del rango válido
    w100 = w.copy()
    for col in selected:
        s = w100[col].dropna()
        if s.empty:
            continue
        base = s.iloc[0]
        w100[col] = (w100[col] / base) * 100.0

    for i, col in enumerate(selected):
        s = w100[col].dropna()
        if s.empty:
            continue
        fig.add_scatter(x=s.index, y=s.values, mode="lines",
                        name=col, line=dict(color=colors[i % len(colors)]))

    fig.update_yaxes(title="Índice (Base=100)")
    title = f"{' vs '.join(selected)} — Base 100 (desde el primer dato del rango)"

elif modo == "Mismo eje" or len(selected) == 1:
    # Una sola escala para todo
    for i, col in enumerate(selected):
        s = w[col].dropna()
        if s.empty:
            continue
        fig.add_scatter(x=s.index, y=s.values, mode="lines",
                        name=col, line=dict(color=colors[i % len(colors)]))
    fig.update_yaxes(title="Valor")
    title = " vs ".join(selected)

else:  # Doble eje Y (y hay 2 series)
    s_left = w[selected[0]].dropna()
    s_right = w[selected[1]].dropna()

    fig.add_scatter(x=s_left.index, y=s_left.values, name=selected[0],
                    mode="lines", line=dict(color=colors[0]), yaxis="y1")
    fig.add_scatter(x=s_right.index, y=s_right.values, name=selected[1],
                    mode="lines", line=dict(color=colors[1]), yaxis="y2")

    # ticks izquierdos "lindos"
    lmin, lmax = float(np.nanmin(s_left)), float(np.nanmax(s_left))
    left_ticks = nice_ticks(lmin, lmax, max_ticks=7)
    fig.update_yaxes(
        title=selected[0],
        tickmode="array", tickvals=left_ticks,
        showgrid=True, side="left", overlaying=None
    )

    # ticks derechos alineados a las líneas horizontales
    rmin, rmax = float(np.nanmin(s_right)), float(np.nanmax(s_right))
    right_ticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)
    fig.update_yaxes(
        title=selected[1],
        tickmode="array", tickvals=right_ticks,
        showgrid=False, side="right", overlaying="y",
        range=[r0, r1], tickformat=".2s"
    )
    title = f"{selected[0]} vs {selected[1]} (doble eje Y)"

# Layout común
fig.update_layout(
    title=title,
    xaxis=dict(title="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside"),
    legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    height=620, margin=dict(t=50, b=80, l=60, r=60),
)

st.plotly_chart(fig, use_container_width=True)

# Nota breve
if modo == "Doble eje Y" and len(selected) == 2:
    st.caption("Nota: el eje derecho se escala para que sus ticks caigan sobre las líneas de grilla "
               "del eje izquierdo; los valores no tienen por qué coincidir con los del eje izquierdo.")
elif modo == "Base 100":
    st.caption("Nota: cada serie se reescala a 100 en su primer dato dentro del rango seleccionado.")
