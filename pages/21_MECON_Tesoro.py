# pages/21_MECON_Tesoro.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from ui import inject_css, range_controls, series_picker, clean_label, looks_percent
from mecon_utils import load_mecon_long, add_series_to_catalog, fetch_mecon_to_disk

st.set_page_config(page_title="MECON – Tesoro / Indicadores", layout="wide")
inject_css()
st.title("🏛️ MECON – Tesoro / Indicadores")

st.markdown("Series del **Ministerio de Economía / datos.gob.ar** guardadas localmente. Podés agregar IDs desde la API pública de series.")

# ---------------------------
# Panel para agregar series
# ---------------------------
with st.expander("➕ Agregar serie desde apis.datos.gob.ar/series", expanded=True):
    col1, col2 = st.columns([0.6, 0.4])
    with col1:
        serie_id = st.text_input("ID de la serie (campo 'ids')", value="", placeholder="p.ej. sspm_mercado_captaciones_tasa_badlar_tna")
        label = st.text_input("Etiqueta amigable (opcional)", value="")
    with col2:
        unidad = st.text_input("Unidad (opcional)", value="")
        if st.button("Guardar en catálogo y descargar", use_container_width=True):
            if serie_id.strip():
                add_series_to_catalog(label or serie_id, serie_id.strip(), provider="datos_gobar", unidad=(unidad or None))
                df_new = fetch_mecon_to_disk()
                st.success(f"Serie agregada y cache actualizada. Total filas: {len(df_new):,}")
            else:
                st.warning("Ingresá al menos el ID de la serie.")

# ---------------------------
# Cargar datos locales
# ---------------------------
df = load_mecon_long()
if df.empty:
    st.info("Aún no hay series MECON guardadas. Agregá alguna arriba.")
    st.stop()

# Opciones limpias
vars_all = sorted(df["descripcion"].dropna().unique().tolist())
pretty = {v: clean_label(v) for v in vars_all}
options_pretty = [pretty[v] for v in vars_all]
map_pretty_to_raw = {pretty[v]: v for v in vars_all}

# Picker
sel_pretty = series_picker(
    options=options_pretty,
    default=options_pretty[:3] if options_pretty else None,
    max_selections=3,
    key="mecon",
    title="Elegí hasta 3 series",
    subtitle="Estas series vienen del catálogo local (datos.gob.ar/series).",
    show_chips=False,
)
sel = [map_pretty_to_raw[x] for x in sel_pretty]
if not sel:
    st.info("Elegí al menos una serie para comenzar.")
    st.stop()

# Pivot
wide_full = (
    df[df["descripcion"].isin(sel)]
    .pivot(index="fecha", columns="descripcion", values="valor")
    .sort_index()
)

# Rango y frecuencia
dmin, dmax = wide_full.index.min(), wide_full.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="mecon")
freq = "D" if freq_label.startswith("Diaria") else "M"

wide_vis = wide_full.loc[d_ini:d_fin]
if freq == "M":
    wide_vis = wide_vis.resample("M").last()
wide_vis = wide_vis.dropna(how="all")
if wide_vis.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# Heurística ejes
left_series  = [n for n in sel if looks_percent(n)]
right_series = [n for n in sel if n not in left_series]
if not left_series:
    left_series = sel[:]
    right_series = []

# Figura
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

for i, name in enumerate(left_series):
    s = wide_vis[name].dropna()
    if s.empty: continue
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=clean_label(name), line=dict(width=2, color=palette[i % len(palette)]), yaxis="y",
        hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

for j, name in enumerate(right_series):
    s = wide_vis[name].dropna()
    if s.empty: continue
    color = palette[(len(left_series)+j) % len(palette)]
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=clean_label(name), line=dict(width=2, color=color), yaxis="y2",
        hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
    ))

fig.update_layout(template="atlas_dark", height=620, margin=dict(t=30, b=80, l=70, r=90), showlegend=True)
fig.update_xaxes(title_text="Fecha")
fig.update_yaxes(title_text="Eje izq", showgrid=True, gridcolor="#1F2937")
if right_series:
    fig.update_layout(yaxis2=dict(title="Eje der", overlaying="y", side="right", showgrid=False))

st.plotly_chart(fig, use_container_width=True)
