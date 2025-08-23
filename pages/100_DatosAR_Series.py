# pages/100_DatosAR_Series.py
from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from ui import inject_css, range_controls, series_picker, clean_label, looks_percent, kpi
from datosar_utils import (
    load_datosar_long,
    datosar_search,
    presets_catalog,
    upsert_allowlist,
    read_allowlist,
    fetch_datosar_to_disk,
)

st.set_page_config(page_title="Series de Datos Argentina", layout="wide")
inject_css()
st.title("📊 Series de Datos Argentina")

st.caption("Buscá, agregá al catálogo local y graficá. El fetch nocturno leerá "
           "`data/datosar_allowlist.txt`.")

# =========================
# 1) Colecciones rápidas (presets)
# =========================
presets = presets_catalog()
with st.expander("⚡ Colecciones rápidas (MEcon/Hacienda)", expanded=True):
    cols = st.columns(2)
    chosen: list[str] = []
    for i, (group, items) in enumerate(presets.items()):
        with cols[i % 2]:
            st.markdown(f"**{group}**")
            for it in items:
                ck = st.checkbox(f"{it['label']}", help=it.get("hint", ""), key=f"preset_{it['id']}")
                if ck:
                    chosen.append(it["id"])
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("➕ Agregar seleccionadas", use_container_width=True, disabled=(len(chosen) == 0)):
            upsert_allowlist(chosen)
            # intento bajar de inmediato
            fetch_datosar_to_disk(chosen)
            st.success(f"Agregadas {len(chosen)} al catálogo y descargadas (si existían).")

# =========================
# 2) Buscar en la API
# =========================
with st.expander("🔎 Buscar y agregar series al catálogo local", expanded=True):
    cA, cB = st.columns([3, 1])
    with cA:
        q = st.text_input("Buscar por palabra clave (ej.: resultado primario, gasto total, ingresos, resultado financiero)",
                          value="ingresos")
    with cB:
        lim = st.number_input("Límite de resultados", min_value=10, max_value=200, value=50, step=10)
    if st.button("Buscar", type="primary"):
        try:
            res = datosar_search(q, int(lim))
        except Exception as e:
            res = []
            st.error("Error consultando el endpoint de búsqueda.")
        if not res:
            st.info("Sin resultados (o el endpoint no devolvió nada). Probá otro término.")
        else:
            st.write(f"Resultados: {len(res)}")
            add_ids = []
            for r in res:
                _id = r.get("id") or r.get("series_id") or ""
                title = r.get("title") or r.get("dataset_title") or _id
                org = r.get("publisher", {}).get("name", "")
                st.markdown(f"- **{title}**  \n  `id: {_id}`  · _{org}_")
                if st.button(f"Agregar {_id}", key=f"add_{_id}"):
                    add_ids.append(_id)
            if add_ids:
                upsert_allowlist(add_ids)
                fetch_datosar_to_disk(add_ids)
                st.success(f"Agregadas {len(add_ids)} al catálogo y descargadas.")

# =========================
# 3) Catálogo local → seleccionar y graficar
# =========================
df = load_datosar_long()
if df.empty:
    st.warning("Todavía no hay datos locales de Datos Argentina. Buscá y agregá series arriba o corré el fetch `scripts/fetch_datosar.py`.")
    st.stop()

# Opciones locales
local_ids = sorted(df["id"].unique().tolist())
# labels amigables
options_lbl = []
for _id in local_ids:
    titulo = df.loc[df["id"] == _id, "titulo"].dropna().iloc[0] if not df.loc[df["id"] == _id, "titulo"].dropna().empty else _id
    options_lbl.append(f"{clean_label(titulo)} · [{_id}]")

lbl2id = {lbl: _id for lbl, _id in zip(options_lbl, local_ids)}

sel_lbls = series_picker(
    options_lbl,
    default=options_lbl[:3] if len(options_lbl) >= 3 else options_lbl,
    max_selections=3,
    key="datosar_pick",
    title="Elegí hasta 3 series",
    subtitle="Podés combinar razones y niveles; si mezclás porcentaje con niveles usaremos doble eje.",
    show_chips=False,
)

sel_ids = [lbl2id[lbl] for lbl in sel_lbls] if sel_lbls else []
if not sel_ids:
    st.info("Elegí al menos una serie del catálogo local.")
    st.stop()

# Pivot de selección
wide_full = (
    df[df["id"].isin(sel_ids)]
    .pivot(index="fecha", columns="id", values="valor")
    .sort_index()
)

# Rango + frecuencia
dmin, dmax = wide_full.index.min(), wide_full.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="datosar")
freq = "D" if freq_label.startswith("Diaria") else "M"

wide_vis = wide_full.loc[d_ini:d_fin]
if freq == "M":
    wide_vis = wide_vis.resample("M").last()
wide_vis = wide_vis.dropna(how="all")
if wide_vis.empty:
    st.warning("El rango/frecuencia seleccionados dejan las series sin datos.")
    st.stop()

# Heurística ejes
left_ids  = [i for i in sel_ids if looks_percent(df.loc[df["id"] == i, "titulo"].iloc[0] if not df.loc[df["id"] == i, "titulo"].empty else i)]
right_ids = [i for i in sel_ids if i not in left_ids]
if not left_ids:
    left_ids, right_ids = sel_ids[:], []

# Figura
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

def label_for(_id: str) -> str:
    t = df.loc[df["id"] == _id, "titulo"].dropna()
    return clean_label(t.iloc[0]) if not t.empty else _id

legend_left, legend_right = [], []

for i, _id in enumerate(left_ids):
    s = wide_vis[_id].dropna()
    if s.empty: continue
    color = palette[i % len(palette)]
    legend_left.append((label_for(_id), color))
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines",
                             name=_id, line=dict(width=2, color=color), yaxis="y",
                             hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>"))

for j, _id in enumerate(right_ids):
    s = wide_vis[_id].dropna()
    if s.empty: continue
    color = palette[(len(left_ids) + j) % len(palette)]
    legend_right.append((label_for(_id), color))
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines",
                             name=_id, line=dict(width=2, color=color), yaxis="y2",
                             hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>"))

fig.update_layout(template="atlas_dark", height=620,
                  margin=dict(t=30, b=120, l=70, r=90),
                  showlegend=False, uirevision=None)
fig.update_xaxes(title_text="Fecha",
                 showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")

fig.update_yaxes(title_text="Eje izq", showline=True, linewidth=1, linecolor="#E5E7EB",
                 showgrid=True, gridcolor="#1F2937", autorange=True, tickmode="auto",
                 zeroline=False)

if right_ids:
    fig.update_layout(yaxis2=dict(title="Eje der", overlaying="y", side="right",
                                  showline=True, linewidth=1, linecolor="#E5E7EB",
                                  showgrid=False, autorange=True, tickmode="auto",
                                  zeroline=False))

# Log toggles
lc1, lc2, _ = st.columns([1,1,2])
with lc1:
    log_left = st.toggle("Escala log (eje izq)", value=False, key="log_left_datosar")
with lc2:
    log_right = st.toggle("Escala log (eje der)", value=False, key="log_right_datosar", disabled=(len(right_ids)==0))
if log_left:
    fig.update_yaxes(type="log")
if log_right and right_ids:
    fig.update_layout(yaxis2=dict(type="log"))

st.plotly_chart(fig, use_container_width=True)

# Leyenda split
rows_html = []
if legend_left:
    left_items = "".join(f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>'
                         for lbl, c in legend_left)
    rows_html.append(f'<div class="col"><div class="hdr">Eje izquierdo</div>{left_items}</div>')
if legend_right:
    right_items = "".join(f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>'
                          for lbl, c in legend_right)
    rows_html.append(f'<div class="col right"><div class="hdr">Eje derecho</div>{right_items}</div>')
if rows_html:
    st.markdown("<div class='split-legend'>" + ("".join(rows_html)) + "</div>", unsafe_allow_html=True)
