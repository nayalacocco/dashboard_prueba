# pages/90_Macro_Resumen.py
import os
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import inject_css, range_controls, kpi_quad

st.set_page_config(page_title="Resumen macro – núcleo", layout="wide")
inject_css()
st.title("📈 Resumen macro – núcleo (BCRA + placeholders)")

DATA_PARQ = Path("data/macro_core_long.parquet")
DATA_CSV  = Path("data/macro_core_long.csv")

# ----------------------------
# Carga robusta + normalización
# ----------------------------
@st.cache_data
def load_long():
    path = DATA_PARQ if DATA_PARQ.exists() else (DATA_CSV if DATA_CSV.exists() else None)
    if path is None:
        return pd.DataFrame()

    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    # Normalizo tipos
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    # Mapear 'serie' -> 'indicador' (si viniera así del builder)
    if "indicador" not in df.columns and "serie" in df.columns:
        df = df.rename(columns={"serie": "indicador"})
    # Crear 'titulo' si no existe
    if "titulo" not in df.columns:
        df["titulo"] = df["indicador"]

    # Asegurar columnas mínimas
    for col in ("fuente", "nota"):
        if col not in df.columns:
            df[col] = ""

    # Limpio NaNs obvios
    df = df.dropna(subset=["fecha", "indicador", "valor"])
    return df

df = load_long()
if df.empty:
    st.warning(
        "Aún no encontré `data/macro_core_long.parquet` ni `data/macro_core_long.csv`.\n\n"
        "Corré primero:\n"
        "1) `scripts/fetch_bcra.py`\n"
        "2) `scripts/build_macro_core.py`"
    )
    st.stop()

# -------------------------------------------------------------------------------------------------
# Descubrimiento flexible de las 2 series núcleo (por si cambian IDs/etiquetas entre builds)
# -------------------------------------------------------------------------------------------------
def find_indicador(df: pd.DataFrame, needles: list[str]) -> str | None:
    """Devuelve el valor exacto de df['indicador'] que 'contenga' alguno de los patrones."""
    if "indicador" not in df.columns:
        return None
    col = df["indicador"].astype(str).str.lower()
    for needle in needles:
        m = col.str.contains(needle.lower(), na=False)
        if m.any():
            return df.loc[m, "indicador"].iloc[0]
    return None

# Patrones típicos (podés sumar más)
key_reservas = find_indicador(df, ["reservas_brutas_bcra", "reservas brutas", "reservas_bcra", "reservas"])
key_pasivos  = find_indicador(df, ["pasivos_remunerados_bcra", "pases pasivos", "leliq", "pasivos remunerados"])

# Armamos el "catálogo" visible (solo las que encontremos)
indicadores = {}
if key_reservas:
    # título preferente = el 'titulo' que trae el archivo; si falta, uso el indicador crudo
    t = df.loc[df["indicador"] == key_reservas, "titulo"]
    indicadores[key_reservas] = (t.iloc[0] if not t.empty else "Reservas brutas BCRA")
if key_pasivos:
    t = df.loc[df["indicador"] == key_pasivos, "titulo"]
    indicadores[key_pasivos] = (t.iloc[0] if not t.empty else "Pasivos remunerados (LELIQ+Pases) – BCRA")

if not indicadores:
    st.error(
        "No pude identificar las series núcleo en el archivo. "
        "Revisá que el builder exporte al menos 'reservas brutas' y 'pasivos remunerados'."
    )
    st.stop()

# Opciones que ve el usuario (por 'titulo')
opts = [v for v in indicadores.values()]
sel = st.multiselect(
    "Elegí hasta 3 series",
    options=opts,
    default=opts[: min(2, len(opts))],
    max_selections=3
)
if not sel:
    st.info("Seleccioná al menos una serie.")
    st.stop()

# Map de título -> indicador real
title_to_key = {}
for k, v in indicadores.items():
    title_to_key[v] = k

keys = [title_to_key[t] for t in sel if t in title_to_key]

# ----------------------------
# Armado wide y controles
# ----------------------------
wide = (
    df[df["indicador"].isin(keys)]
    .pivot(index="fecha", columns="titulo", values="valor")
    .sort_index()
)

if wide.empty:
    st.warning("No hay datos para las series seleccionadas en el rango disponible.")
    st.stop()

dmin, dmax = wide.index.min(), wide.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="macro_core", show_government=False)
vis = wide.loc[d_ini:d_fin].dropna(how="all")
if freq_label.startswith("Mensual"):
    vis = vis.resample("M").last()

# ----------------------------
# Chart
# ----------------------------
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]
for i, name in enumerate(vis.columns):
    s = vis[name].dropna()
    if s.empty:
        continue
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=name, line=dict(width=2, color=palette[i % 3]),
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>"
        )
    )
fig.update_layout(template="atlas_dark", height=620, margin=dict(t=30, b=80, l=70, r=60))
fig.update_xaxes(title_text="Fecha")
fig.update_yaxes(title_text="Valor")

st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# KPIs (último + MoM + YoY + Δ)
# ----------------------------
from bcra_utils import resample_series, compute_kpis

palette_cycle = ["#60A5FA", "#F87171", "#34D399"]
for idx, name in enumerate(vis.columns):
    full = wide[name].dropna()
    visible = resample_series(
        vis[name].dropna(),
        freq=("D" if freq_label.startswith("Diaria") else "M"),
        how="last"
    ).dropna()
    mom, yoy, d_per = compute_kpis(full, visible)
    last_val = visible.iloc[-1] if not visible.empty else None
    kpi_quad(
        title=name,
        color=palette_cycle[idx % len(palette_cycle)],
        last_value=last_val,
        is_percent=False,
        mom=mom, yoy=yoy, d_per=d_per,
        tip_last="Último dato del rango visible.",
        tip_mom="Δ vs mes anterior (último dato mensual).",
        tip_yoy="Δ vs mismo mes del año previo.",
        tip_per="Δ entre el primero y el último del período visible.",
    )
