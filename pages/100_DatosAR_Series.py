# pages/100_DatosAR_Series.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from ui import inject_css, range_controls, clean_label, looks_percent, kpi_quad, series_picker
from datosar_utils import load_datosar_long, search_datosar, add_and_fetch, read_allowlist

st.set_page_config(page_title="Series – Datos Argentina", layout="wide")
inject_css()
st.title("📊 Series de Datos Argentina")

st.caption("Buscá, agregá al catálogo local y graficá. El fetch nocturno leerá `data/datosar_allowlist.txt`.")

# -------------------------
# Panel de búsqueda / alta
# -------------------------
with st.expander("🔎 Buscar y agregar series al catálogo local", expanded=False):
    qcol, lcol = st.columns([2,1])
    with qcol:
        q = st.text_input("Buscar por palabra clave (ej.: resultado primario, gasto total, ingresos, resultado financiero)", value="")
    with lcol:
        limit = st.number_input("Límite de resultados", min_value=5, max_value=200, value=50, step=5)
    if st.button("Buscar"):
        if not q.strip():
            st.warning("Escribí un término de búsqueda.")
        else:
            results = search_datosar(q.strip(), int(limit))
            if not results:
                st.info("Sin resultados (o el endpoint de búsqueda de la API no devolvió nada). Probá otro término.")
            else:
                st.success(f"{len(results)} resultados")
                # Selección
                opts = [f"[{sid}] {title} — {src}" for sid, title, src in results]
                pick = st.multiselect("Elegí series para agregar", options=opts)
                if pick and st.button("➕ Agregar a catálogo y descargar"):
                    ids = [p.split("]")[0][1:] for p in pick]
                    with st.spinner("Agregando y descargando…"):
                        add_and_fetch(ids)
                    st.success("Listo. Actualizá la página para ver los nuevos datos si no aparecen automáticamente.")

st.divider()

# -------------------------
# Carga local
# -------------------------
df = load_datosar_long()
if df.empty:
    st.warning("Todavía no hay datos locales de Datos Argentina. Buscá y agregá series arriba o corré el fetch `scripts/fetch_datosar.py`.")
    st.stop()

# Labels
id2desc = (
    df.dropna(subset=["descripcion"])
      .drop_duplicates(subset=["id"])
      .set_index("id")["descripcion"]
      .to_dict()
)
all_ids = sorted(df["id"].unique().tolist())
options = [f"[{sid}] {clean_label(id2desc.get(sid, sid))}" for sid in all_ids]
lab2id  = {opt: opt.split("]")[0][1:] for opt in options}

# Defaults: si hay allowlist, tomamos hasta 3 primeros
allow = read_allowlist()
defaults = [f"[{sid}] {clean_label(id2desc.get(sid, sid))}" for sid in allow[:3] if sid in id2desc]

sel_labels = series_picker(
    options,
    default=(defaults if defaults else options[:3]),
    max_selections=3,
    key="datosar",
    title="Elegí hasta 3 series",
    subtitle="Podés mezclar indicadores de organismos distintos. Si hay % y niveles, activamos doble eje.",
    show_chips=False,
)
if not sel_labels:
    st.info("Elegí al menos una serie para comenzar.")
    st.stop()

sel_ids = [lab2id[x] for x in sel_labels]

# -------------------------
# Ancho para gráfico
# -------------------------
wide_full = (
    df[df["id"].isin(sel_ids)]
      .pivot(index="fecha", columns="id", values="valor")
      .sort_index()
)
if wide_full.empty:
    st.warning("No hay datos para esas series.")
    st.stop()

# -------------------------
# Rango + frecuencia
# -------------------------
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

# -------------------------
# Ejes
# -------------------------
left_ids  = [sid for sid in sel_ids if looks_percent(id2desc.get(sid, sid))]
right_ids = [sid for sid in sel_ids if sid not in left_ids]
if not left_ids:
    left_ids, right_ids = sel_ids[:], []

# -------------------------
# Figura
# -------------------------
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

for i, sid in enumerate(left_ids):
    s = wide_vis[sid].dropna()
    if s.empty: 
        continue
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=clean_label(id2desc.get(sid, sid)),
            line=dict(width=2, color=palette[i % len(palette)]),
            yaxis="y",
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

for j, sid in enumerate(right_ids):
    s = wide_vis[sid].dropna()
    if s.empty: 
        continue
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=clean_label(id2desc.get(sid, sid)),
            line=dict(width=2, color=palette[(len(left_ids)+j) % len(palette)]),
            yaxis="y2",
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

fig.update_layout(
    template="atlas_dark",
    height=620,
    margin=dict(t=30, b=80, l=70, r=90),
    showlegend=True,
)
fig.update_xaxes(title_text="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB")
fig.update_yaxes(
    title_text="Eje izq",
    showline=True, linewidth=1, linecolor="#E5E7EB",
    showgrid=True, gridcolor="#1F2937",
    tickformat=(".0f" if left_ids else "~s"),
    zeroline=False,
)
if right_ids:
    fig.update_layout(
        yaxis2=dict(
            title="Eje der",
            overlaying="y", side="right",
            showline=True, linewidth=1, linecolor="#E5E7EB",
            showgrid=False, tickformat="~s", zeroline=False,
        )
    )
st.plotly_chart(fig, use_container_width=True)

# -------------------------
# KPIs (cuádruple con “último dato”)
# -------------------------
def compute_pct_changes(full: pd.Series, visible: pd.Series):
    full = full.dropna()
    vis  = visible.dropna()
    if vis.empty:
        return None, None, None, None
    last = vis.iloc[-1]
    mom = (vis.iloc[-1] / vis.iloc[-2] - 1) * 100 if len(vis) >= 2 else None
    yoy = (vis.iloc[-1] / vis.shift(12).iloc[-1] - 1) * 100 if len(vis) >= 13 else None
    dper = (vis.iloc[-1] / vis.iloc[0] - 1) * 100 if len(vis) >= 2 else None
    return float(last), (float(mom) if mom is not None else None), (float(yoy) if yoy is not None else None), (float(dper) if dper is not None else None)

palette_cycle = ["#60A5FA", "#F87171", "#34D399"]
for idx, sid in enumerate(sel_ids):
    name = clean_label(id2desc.get(sid, sid))
    full_s = df[df["id"] == sid].set_index("fecha")["valor"].sort_index().astype(float)
    vis_s  = wide_vis[sid].dropna().astype(float)
    last, mom, yoy, dper = compute_pct_changes(full_s, vis_s)
    is_pct = looks_percent(id2desc.get(sid, sid))
    color  = palette_cycle[idx % len(palette_cycle)]
    kpi_quad(
        title=name, color=color,
        last_value=last, is_percent=is_pct,
        mom=mom, yoy=yoy, d_per=dper,
        tip_last="Último dato visible (rango/frecuencia elegidos).",
        tip_mom="Variación del último dato vs periodo previo del rango.",
        tip_yoy="Variación vs mismo periodo 12 meses atrás.",
        tip_per="Variación del primer al último dato en el rango visible.",
    )
