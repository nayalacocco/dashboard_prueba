# pages/21_MECON_Tesoro.py
from __future__ import annotations

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from typing import List, Dict

from ui import inject_css, range_controls, kpi_triplet, series_picker
from mecon_utils import series_search, series_get  # <- tu helper ya creado

# ---------------------------------------
# Setup
# ---------------------------------------
st.set_page_config(page_title="MECON / Tesoro – Series", layout="wide")
inject_css()
st.title("🏛️ MECON / Tesoro")

st.caption(
    "Series de tiempo oficiales (API Datos Argentina). Podés buscar, seleccionar hasta 6 series, "
    "ajustar rango y frecuencia, y ver un gráfico combinado con KPIs."
)

# ---------------------------------------
# Helpers
# ---------------------------------------
def _meta_label(m: Dict) -> str:
    """Nombre 'lindo' a partir del metadata de la API."""
    # Campo 'title' suele venir muy bien. Si no, fallback a dataset_title + id
    title = m.get("title") or m.get("field", "")
    ds = m.get("dataset_title") or ""
    units = m.get("units") or ""
    if units:
        units = f" ({units})"
    if title and ds:
        return f"{title}{units} – {ds}"
    if title:
        return f"{title}{units}"
    return f"{m.get('id','(sin id)')}{units}"

def _api_to_df(payload) -> pd.DataFrame:
    """
    Convierte la respuesta de /series en DataFrame:
    - index: fecha (datetime)
    - columnas: id de cada serie
    """
    data_rows = payload.get("data", [])
    meta = payload.get("meta", [])
    if not data_rows or not meta:
        return pd.DataFrame()

    # La matriz 'data' viene como [fecha, v1, v2, ...]
    # La fecha suele venir "YYYY-MM-DD" o "YYYY-MM". Parse automático.
    cols = ["fecha"] + [m["id"] for m in meta]
    df = pd.DataFrame(data_rows, columns=cols)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.set_index("fecha").sort_index()

    # Conservar solo numéricos
    for m in meta:
        sid = m["id"]
        df[sid] = pd.to_numeric(df[sid], errors="coerce")

    return df

def _looks_percent(meta_item: Dict) -> bool:
    """Heurística para decidir si la serie parece porcentaje."""
    txt = (" ".join([
        meta_item.get("title",""),
        meta_item.get("field_description",""),
        meta_item.get("units",""),
    ])).lower()
    tokens = ["%", "variación", "variacion", "yoy", "mom", "tna", "tea", "interanual", "mensual", "porcentaje"]
    return any(t in txt for t in tokens) or meta_item.get("units","").strip() == "%"

# ---------------------------------------
# Buscador (API /search) + selección
# ---------------------------------------
with st.container():
    st.subheader("🔎 Buscar series")
    qcol, ncol = st.columns([0.8, 0.2])
    with qcol:
        q = st.text_input("Texto de búsqueda", "resultado primario base caja", placeholder="Ej: deuda pública, resultado fiscal, intereses, recaudación…")
    with ncol:
        page_size = st.number_input("Límites", min_value=10, max_value=200, step=10, value=50, help="Cantidad máx. de resultados.")

    # Ejecuta búsqueda
    res = series_search(q, page_size=page_size)
    data = res.get("data", [])

    # Mapeo id -> label bonito
    id2label = {}
    for m in data:
        try:
            mid = m["id"]
        except KeyError:
            continue
        id2label[mid] = _meta_label(m)

    options = [id2label[k] for k in id2label.keys()]
    # Preselección: si no hay nada, tomamos las 2 primeras
    default_labels = options[:2] if options else []

    st.write("Resultados:", len(options))
    sel_labels = series_picker(
        options=options,
        default=default_labels,
        max_selections=6,
        key="mecon",
        title="Elegí hasta 6 series",
        subtitle="Los títulos incluyen la unidad y el dataset de origen.",
        show_chips=True,
    )

    # Traduzco a IDs
    label2id = {v: k for k, v in id2label.items()}
    sel_ids = [label2id[lbl] for lbl in sel_labels if lbl in label2id]

if not sel_ids:
    st.info("Elegí al menos una serie del buscador para continuar.")
    st.stop()

# ---------------------------------------
# Traer datos de las series elegidas
# ---------------------------------------
# Primero un GET sin recorte para conocer sus metadatos (y decidir % vs niveles)
payload_full = series_get(sel_ids, metadata="full")
meta_full = payload_full.get("meta", [])
id_is_percent = {m["id"]: _looks_percent(m) for m in meta_full}

# Rango + frecuencia (igual que en BCRA)
df_all = _api_to_df(payload_full)
dmin, dmax = df_all.index.min(), df_all.index.max()
if pd.isna(dmin) or pd.isna(dmax):
    st.warning("Las series no tienen datos.")
    st.stop()

d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="mecon", show_government=True)
collapse = "day" if freq_label.startswith("Diaria") else "month"

# Traigo ya colapsado y recortado (optimiza)
payload = series_get(sel_ids, start=d_ini.isoformat(), end=d_fin.isoformat(), collapse=collapse, metadata="full")
meta = payload.get("meta", [])
if not meta:
    st.warning("No hay datos para el rango/frecuencia seleccionados.")
    st.stop()

w = _api_to_df(payload)
w = w.dropna(how="all")
if w.empty:
    st.warning("No hay datos disponibles en este rango/frecuencia.")
    st.stop()

# ---------------------------------------
# Separar % (izq) vs niveles (der)
# ---------------------------------------
left_ids  = [m["id"] for m in meta if id_is_percent.get(m["id"], False)]
right_ids = [m["id"] for m in meta if m["id"] not in left_ids]
if not left_ids:
    # Si ninguna parece %, dejo todo a la izquierda
    left_ids = [m["id"] for m in meta]
    right_ids = []

# ---------------------------------------
# Gráfico
# ---------------------------------------
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399", "#A78BFA", "#F59E0B", "#06B6D4"]

def _label_by_id(sid: str) -> str:
    m = next((mm for mm in meta if mm["id"] == sid), None)
    return _meta_label(m) if m else sid

legend_left = []
legend_right = []

# Izquierda
for i, sid in enumerate(left_ids):
    s = w[sid].dropna()
    if s.empty: continue
    color = palette[i % len(palette)]
    legend_left.append((_label_by_id(sid), color))
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=_label_by_id(sid),
            line=dict(width=2, color=color),
            yaxis="y",
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

# Derecha
for j, sid in enumerate(right_ids):
    s = w[sid].dropna()
    if s.empty: continue
    color = palette[(len(left_ids) + j) % len(palette)]
    legend_right.append((_label_by_id(sid), color))
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=_label_by_id(sid),
            line=dict(width=2, color=color),
            yaxis="y2",
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

fig.update_layout(
    template="atlas_dark",
    height=620,
    margin=dict(t=30, b=120, l=70, r=90),
    showlegend=False,
    uirevision=None,
)

fig.update_xaxes(
    title_text="Fecha",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
)

fig.update_yaxes(
    title_text="Eje izq",
    showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
    showgrid=True, gridcolor="#1F2937",
    autorange=True,
    tickmode="auto",
    tickformat=(".0f" if left_ids else "~s"),
    zeroline=False,
)

if right_ids:
    fig.update_layout(
        yaxis2=dict(
            title="Eje der",
            overlaying="y", side="right",
            showline=True, linewidth=1, linecolor="#E5E7EB",
            showgrid=False,
            autorange=True,
            tickmode="auto",
            tickformat="~s",
            zeroline=False,
        )
    )

# Log toggles
c1, c2, _ = st.columns([1,1,2])
with c1:
    log_left = st.toggle("Escala log (eje izq)", value=False, key="log_left_mecon")
with c2:
    log_right = st.toggle("Escala log (eje der)", value=False, key="log_right_mecon", disabled=(len(right_ids)==0))
if log_left:
    fig.update_yaxes(type="log")
if log_right and right_ids:
    fig.update_layout(yaxis2=dict(type="log"))

st.plotly_chart(fig, use_container_width=True)

# Leyenda split
if legend_left or legend_right:
    st.markdown(
        """
        <style>
          .split-legend { display:flex; flex-wrap:wrap; gap:24px; justify-content:space-between; margin-top:-8px; margin-bottom:10px; }
          .split-legend .col { flex:1 1 380px; }
          .split-legend .col.right { text-align:right; }
          .split-legend .hdr { color:#9CA3AF; font-size:.9rem; margin-bottom:6px; }
          .split-legend .li { color:#E5E7EB; font-size:.95rem; margin:4px 0; display:flex; align-items:center; gap:8px; }
          .split-legend .col.right .li { justify-content:flex-end; }
          .split-legend .dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    rows = []
    if legend_left:
        items = "".join(f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>' for lbl, c in legend_left)
        rows.append(f'<div class="col"><div class="hdr">Eje izquierdo</div>{items}</div>')
    if legend_right:
        items = "".join(f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>' for lbl, c in legend_right)
        rows.append(f'<div class="col right"><div class="hdr">Eje derecho</div>{items}</div>')
    st.markdown("<div class='split-legend'>" + "".join(rows) + "</div>", unsafe_allow_html=True)

# ---------------------------------------
# KPIs (último valor, MoM, YoY, Δ)
# Reutilizamos kpi_triplet mostrando % cuando tiene sentido
# ---------------------------------------
def _kpis_for(sid: str, color: str):
    s_full = w[sid].dropna()
    if s_full.empty:
        return
    # Para consistencia con tu compute_kpis de BCRA, calculamos manual:
    # - mom: último vs mes previo (si hay frecuencia mensual)
    # - yoy: último vs 12 meses atrás (si hay)
    # - d_per: delta % entre primer y último del rango visible
    last = s_full.iloc[-1]
    # MoM
    mom = None
    if len(s_full) >= 2:
        prev = s_full.iloc[-2]
        if pd.notna(prev) and prev != 0:
            mom = (last/prev - 1) * 100
    # YoY
    yoy = None
    if len(s_full) >= 13:
        prev12 = s_full.iloc[-13]
        if pd.notna(prev12) and prev12 != 0:
            yoy = (last/prev12 - 1) * 100
    # Δ período
    d_per = None
    first = s_full.iloc[0]
    if pd.notna(first) and first != 0:
        d_per = (last/first - 1) * 100

    # Título “limpio”
    lab = _label_by_id(sid)

    kpi_triplet(
        title=lab,
        color=color,
        mom=mom, yoy=yoy, d_per=d_per,
        tip_mom="Variación del último dato vs el dato previo en el rango visible.",
        tip_yoy="Variación del último dato vs el mismo período 12 meses atrás (si la frecuencia lo permite).",
        tip_per="Variación total entre primer y último dato del rango visible.",
    )

st.subheader("📈 KPIs por serie")
palette_cycle = ["#60A5FA", "#F87171", "#34D399", "#A78BFA", "#F59E0B", "#06B6D4"]
for idx, sid in enumerate([*left_ids, *right_ids]):
    _kpis_for(sid, palette_cycle[idx % len(palette_cycle)])
