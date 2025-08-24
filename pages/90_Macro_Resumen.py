# pages/90_Macro_Resumen.py
import os
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import inject_css, range_controls, kpi_quad

st.set_page_config(page_title="Resumen macro – núcleo", layout="wide")
inject_css()
st.title("📈 Resumen macro – núcleo (BCRA + DatosAR)")

BCRA_PARQ = Path("data/macro_core_long.parquet")
BCRA_CSV  = Path("data/macro_core_long.csv")
DAR_PARQ  = Path("data/datosar_core_long.parquet")

def _load_any(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    if "valor" in df.columns:
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    # normalizo esquema mínimo
    if "indicador" not in df.columns and "serie" in df.columns:
        df = df.rename(columns={"serie":"indicador"})
    if "titulo" not in df.columns:
        df["titulo"] = df["indicador"]
    if "fuente" not in df.columns:
        df["fuente"] = ""
    return df.dropna(subset=["fecha","indicador","valor"])

@st.cache_data
def load_all():
    bc = _load_any(BCRA_PARQ) if BCRA_PARQ.exists() else _load_any(BCRA_CSV)
    da = _load_any(DAR_PARQ)
    if bc.empty and da.empty:
        return pd.DataFrame()
    return pd.concat([bc, da], ignore_index=True).sort_values(["titulo","fecha"])

df = load_all()
if df.empty:
    st.warning(
        "No hay datos aún. Corré:\n"
        "• Workflow BCRA (para macro_core)\n"
        "• Workflow DatosAR core (5 series)"
    )
    st.stop()

# Opciones: todos los títulos
opciones = sorted(df["titulo"].dropna().unique().tolist())
default_opts = []
# Intento setear defaults amables si existen
prefer = [
    "Reservas brutas BCRA",
    "Pasivos remunerados (LELIQ+Pases) – BCRA",
    "IPC variación mensual (nacional)",
]
for p in prefer:
    if p in opciones and p not in default_opts:
        default_opts.append(p)

sel = st.multiselect("Elegí hasta 3 series", options=opciones,
                     default=(default_opts[:3] if default_opts else opciones[:2]),
                     max_selections=3)
if not sel:
    st.info("Seleccioná al menos una serie.")
    st.stop()

wide = (
    df[df["titulo"].isin(sel)]
    .pivot(index="fecha", columns="titulo", values="valor")
    .sort_index()
)
if wide.empty:
    st.warning("No hay datos para las series seleccionadas.")
    st.stop()

dmin, dmax = wide.index.min(), wide.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="macro_core", show_government=False)
vis = wide.loc[d_ini:d_fin].dropna(how="all")
if freq_label.startswith("Mensual"):
    vis = vis.resample("M").last()

# Chart
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]
for i, name in enumerate(vis.columns):
    s = vis[name].dropna()
    if s.empty:
        continue
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        name=name, line=dict(width=2, color=palette[i % 3]),
        hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>"
    ))
fig.update_layout(template="atlas_dark", height=620, margin=dict(t=30,b=80,l=70,r=60))
fig.update_xaxes(title_text="Fecha")
fig.update_yaxes(title_text="Valor")
st.plotly_chart(fig, use_container_width=True)

# KPIs
from bcra_utils import resample_series, compute_kpis
palette_cycle = ["#60A5FA", "#F87171", "#34D399"]
for idx, name in enumerate(vis.columns):
    full = wide[name].dropna()
    visible = resample_series(
        vis[name].dropna(),
        freq=("D" if freq_label.startswith("Diaria") else "M"),
        how="last",
    ).dropna()
    mom, yoy, d_per = compute_kpis(full, visible)
    last_val = visible.iloc[-1] if not visible.empty else None
    st.markdown(" ")
    kpi_quad(
        title=name,
        color=palette_cycle[idx % len(palette_cycle)],
        last_value=last_val,
        is_percent=("variación" in name.lower() or "%" in name.lower()),
        mom=mom, yoy=yoy, d_per=d_per,
        tip_last="Último dato del rango visible.",
        tip_mom="Δ vs mes anterior (último dato mensual).",
        tip_yoy="Δ vs mismo mes del año previo.",
        tip_per="Δ entre el primero y el último del período visible.",
    )
