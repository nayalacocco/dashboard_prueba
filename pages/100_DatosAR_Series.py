# pages/100_DatosAR_Series.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from ui import inject_css, range_controls, kpi_quad, series_picker, clean_label, looks_percent
from datosar_utils import load_catalog, load_series

st.set_page_config(page_title="📊 DatosAR – Series de tiempo", layout="wide")
inject_css()
st.title("📊 DatosAR – Series de tiempo (MEcon / INDEC / Hacienda)")

# ------------------------
# Cargar catálogo
# ------------------------
cat = load_catalog()
if cat.empty:
    st.warning("No encontré el índice de DatosAR. Corré el fetch primero: `scripts/fetch_datosar_catalog.py`.")
    st.stop()

# Filtros
with st.container():
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1, 1])
    with c1:
        org = st.selectbox("Organismo", ["(todos)"] + sorted([x for x in cat["org"].dropna().unique().tolist() if x]), index=0)
    with c2:
        topic = st.selectbox("Tema", ["(todos)"] + sorted([x for x in cat["topic"].dropna().unique().tolist() if x]), index=0)
    with c3:
        freq = st.selectbox("Frecuencia", ["(todas)"] + sorted([x for x in cat["frequency"].dropna().unique().tolist() if x]), index=0)
    with c4:
        unit = st.selectbox("Unidad", ["(todas)"] + sorted([x for x in cat["unit"].dropna().unique().tolist() if x]), index=0)

    q = st.text_input("Buscar por texto", value="", placeholder="resultado primario, gasto, ingresos, inflación, IPC…")

# Aplicar filtros
f = cat.copy()
if org != "(todos)":    f = f[f["org"] == org]
if topic != "(todos)":  f = f[f["topic"] == topic]
if freq != "(todas)":   f = f[f["frequency"] == freq]
if unit != "(todas)":   f = f[f["unit"] == unit]
if q.strip():
    qq = q.strip().lower()
    f = f[f["title"].str.lower().str.contains(qq, na=False)]

# Selector con nombres (no IDs)
options = [f'{r["title"]} · {r["org"]} · {r["frequency"] or "—"}' for _, r in f.iterrows()]
id_by_option = {opt: r["id"] for opt, (_, r) in zip(options, f.iterrows())}

sel_labels = series_picker(
    options=options,
    default=options[:2] if options else None,
    max_selections=3,
    key="datosar",
    title="Elegí hasta 3 series",
    subtitle="Catálogo construido offline (fetch) — sin necesidad de saber IDs.",
    show_chips=False,
)

if not sel_labels:
    st.info("Elegí al menos una serie para comenzar.")
    st.stop()

# Mapear a IDs y nombres bonitos
chosen = [(id_by_option[opt], opt.split(" · ")[0]) for opt in sel_labels]
ids = [c[0] for c in chosen]

# Traer series
data = {}
for sid, title in chosen:
    s = load_series(sid)
    if s.empty:
        continue
    data[title] = s

if not data:
    st.error("Ninguna de las series seleccionadas tiene datos cacheados. Corré el prefetch (seed IDs) o probá con otras.")
    st.stop()

# Wide
df = pd.DataFrame(data)
df = df.sort_index()

# Rango + Frecuencia
dmin, dmax = df.index.min().date(), df.index.max().date()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="datosar")
wide = df.loc[str(d_ini):str(d_fin)]
if "Mensual" in freq_label:
    wide = wide.resample("M").last()
wide = wide.dropna(how="all")
if wide.empty:
    st.warning("El rango/frecuencia seleccionados dejan sin datos.")
    st.stop()

# Heurística ejes
left_names  = [name for name in wide.columns if looks_percent(name)]
right_names = [name for name in wide.columns if name not in left_names]
if not left_names:
    left_names = list(wide.columns)
    right_names = []

# Figura
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

legend_left, legend_right = [], []

for i, name in enumerate(left_names):
    color = palette[i % len(palette)]
    legend_left.append((name, color))
    fig.add_trace(go.Scatter(x=wide.index, y=wide[name], mode="lines",
                             name=name, line=dict(width=2, color=color), yaxis="y",
                             hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>"))

for j, name in enumerate(right_names):
    color = palette[(len(left_names) + j) % len(palette)]
    legend_right.append((name, color))
    fig.add_trace(go.Scatter(x=wide.index, y=wide[name], mode="lines",
                             name=name, line=dict(width=2, color=color), yaxis="y2",
                             hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>"))

fig.update_layout(template="atlas_dark", height=620, margin=dict(t=30, b=120, l=70, r=90), showlegend=False)
fig.update_xaxes(title_text="Fecha", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside")
fig.update_yaxes(title_text="Eje izq", showline=True, linewidth=1, linecolor="#E5E7EB", ticks="outside",
                 showgrid=True, gridcolor="#1F2937", autorange=True, tickmode="auto", tickformat="~s", zeroline=False)
if right_names:
    fig.update_layout(yaxis2=dict(title="Eje der", overlaying="y", side="right", showline=True,
                                  linewidth=1, linecolor="#E5E7EB", showgrid=False, autorange=True,
                                  tickmode="auto", tickformat="~s", zeroline=False))

# Log visual
c1, c2, _ = st.columns([1,1,2])
with c1: log_left = st.toggle("Escala log (eje izq)", value=False, key="log_left_datosar")
with c2: log_right = st.toggle("Escala log (eje der)", value=False, key="log_right_datosar", disabled=(len(right_names)==0))
if log_left:  fig.update_yaxes(type="log")
if log_right: fig.update_layout(yaxis2=dict(type="log"))

st.plotly_chart(fig, use_container_width=True)

# Leyenda split
rows_html = []
if legend_left:
    left_items  = "".join(f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>' for lbl, c in legend_left)
    rows_html.append(f'<div class="col"><div class="hdr">Eje izquierdo</div>{left_items}</div>')
if legend_right:
    right_items = "".join(f'<div class="li"><span class="dot" style="background:{c}"></span>{lbl}</div>' for lbl, c in legend_right)
    rows_html.append(f'<div class="col right"><div class="hdr">Eje derecho</div>{right_items}</div>')
if rows_html:
    st.markdown("<div class='split-legend'>" + ("".join(rows_html)) + "</div>", unsafe_allow_html=True)

# KPIs por serie (cuádruple)
from bcra_utils import resample_series, compute_kpis  # ya los tenés

def kpis_for(name: str, color: str):
    full = df[name].dropna()
    vis  = wide[name].dropna()
    # convertir visible a fin de mes si corresponde
    vis_res = resample_series(vis, freq=("M" if "Mensual" in freq_label else "D"), how="last").dropna()
    mom, yoy, d_per = compute_kpis(full, vis_res)
    last_val = full.dropna().iloc[-1] if not full.dropna().empty else None
    # ¿parece %?
    is_pct = looks_percent(name)
    kpi_quad(
        title=name, color=color,
        last_value=last_val, is_percent=is_pct,
        mom=mom, yoy=yoy, d_per=d_per,
        tip_last="Valor más reciente disponible.",
        tip_mom="Variación del último dato mensual vs el mes previo (fin de mes).",
        tip_yoy="Variación del último dato mensual vs el mismo mes de hace 12 meses.",
        tip_per="Variación entre primer y último dato del rango visible.",
    )

palette_cycle = ["#60A5FA", "#F87171", "#34D399"]
for idx, name in enumerate(wide.columns.tolist()):
    kpis_for(name, palette_cycle[idx % len(palette_cycle)])
