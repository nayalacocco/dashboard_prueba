# pages/100_DatosAR_Series.py
import os
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from typing import Optional, Tuple

from ui import inject_css, range_controls, kpi_quad, clean_label, looks_percent
from bcra_utils import resample_series, compute_kpis  # reutilizamos helpers

st.set_page_config(page_title="Series de Datos Argentina", layout="wide")
inject_css()
st.title("🇦🇷 Series de Datos Argentina")

# ----------------------------
# Rutas de datos locales
# ----------------------------
LONG_PARQUET = "data/datosar_long.parquet"
CAT_PARQUET  = "data/datosar_catalog_meta.parquet"
CAT_CSV      = "data/datosar_catalog.csv"

# ----------------------------
# Carga de catálogo
# ----------------------------
@st.cache_data(show_spinner=False)
def load_catalog() -> pd.DataFrame:
    # 1) Intento catálogo Parquet (si lo tenés generado por fetch)
    if os.path.exists(CAT_PARQUET):
        try:
            cat = pd.read_parquet(CAT_PARQUET)
            # normalizo columnas mínimas
            if "name" not in cat.columns and "descripcion" in cat.columns:
                cat["name"] = cat["descripcion"]
            if "source" not in cat.columns:
                cat["source"] = "parquet"
            return cat
        except Exception:
            pass

    # 2) Fallback: catálogo manual en CSV
    if os.path.exists(CAT_CSV):
        cat = pd.read_csv(CAT_CSV)
        # columnas esperadas: id,name,source,path,units,(group opcional)
        # normalizo mínimos
        if "name" not in cat.columns:
            raise RuntimeError("datosar_catalog.csv debe tener columna 'name'.")
        if "source" not in cat.columns:
            cat["source"] = "csv"
        if "path" not in cat.columns:
            cat["path"] = None
        if "units" not in cat.columns:
            cat["units"] = ""
        if "group" not in cat.columns:
            cat["group"] = "(manual)"
        return cat

    # 3) Nada disponible
    return pd.DataFrame()

# ----------------------------
# Carga del long (si existe)
# ----------------------------
@st.cache_data(show_spinner=False)
def load_long() -> pd.DataFrame:
    if os.path.exists(LONG_PARQUET):
        try:
            df = pd.read_parquet(LONG_PARQUET)
            # se espera: columnas ['fecha','descripcion','valor'] (o similares)
            # normalizo nombres si es necesario
            cols = {c.lower(): c for c in df.columns}
            # fuerza nombres estándar si están presentes con otro casing
            for want in ["fecha", "descripcion", "valor"]:
                if want not in df.columns:
                    # intento mapear por lower
                    for k, v in cols.items():
                        if k == want:
                            df.rename(columns={v: want}, inplace=True)
                            break
            df["fecha"] = pd.to_datetime(df["fecha"])
            return df[["fecha", "descripcion", "valor"]].copy()
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

cat = load_catalog()
long_df = load_long()

# Si no hay nada en absoluto:
if cat.empty and long_df.empty:
    st.warning("Todavía no hay datos locales de DatosAR. Corré el fetch de catálogo + datos o agregá filas a data/datosar_catalog.csv.")
    st.stop()

# ----------------------------
# UI: selector
# ----------------------------
# Grupos si existen (sino, todos)
if "group" in cat.columns:
    grupos = ["(todos)"] + sorted(pd.Series(cat["group"].dropna().unique()).astype(str).tolist())
else:
    grupos = ["(todos)"]

g_sel = st.selectbox("Grupo", grupos, index=0)

if g_sel != "(todos)" and "group" in cat.columns:
    options_df = cat[cat["group"] == g_sel]
else:
    options_df = cat

options = sorted(pd.Series(options_df["name"].dropna().unique()).astype(str).tolist())
sel = st.multiselect("Elegí hasta 3 series", options=options, max_selections=3)

if not sel:
    st.info("Seleccioná al menos una serie (desde el catálogo).")
    st.stop()

# ----------------------------
# Helpers para CSV locales
# ----------------------------
def _detect_date_value_columns(df: pd.DataFrame) -> Tuple[str, str]:
    """
    Heurística simple para encontrar columnas de fecha y de valor en un CSV arbitrario.
    - Busca nombres usuales de fecha.
    - Para el valor toma la primera columna numérica 'fuerte' distinta de la fecha,
      o la segunda columna si solo hay dos.
    """
    # candidatos de fecha
    date_cands = ["fecha", "date", "periodo", "period", "indice_tiempo", "time", "mes", "anio_mes"]
    cols_lower = {c.lower(): c for c in df.columns}

    date_col = None
    for d in date_cands:
        if d in cols_lower:
            date_col = cols_lower[d]
            break
    if date_col is None:
        # si no hay una clara, uso la primera columna
        date_col = df.columns[0]

    # valor: priorizo columnas numéricas
    value_col = None
    for c in df.columns:
        if c == date_col:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            value_col = c
            break
    if value_col is None:
        # si nada numérico, intento la segunda columna
        if len(df.columns) >= 2:
            value_col = df.columns[1]
        else:
            value_col = df.columns[0]  # fallback raro

    return date_col, value_col

@st.cache_data(show_spinner=False)
def load_series_from_csv(path: str, series_name: str) -> pd.Series:
    if not os.path.exists(path):
        raise FileNotFoundError(f"No encontré el archivo CSV: {path}")
    df = pd.read_csv(path)
    # detecto columnas
    date_col, value_col = _detect_date_value_columns(df)
    # parseo fechas
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)
    # aseguro numérico
    s = pd.to_numeric(df[value_col], errors="coerce")
    s.index = df[date_col].values
    s.name = series_name
    s = s.dropna()
    return s

def load_one_series(row: pd.Series) -> Optional[pd.Series]:
    """
    Carga una serie según su origen:
    - 'csv' => lee path local
    - 'parquet' => la busca en long_df por 'name' (o 'id' si existiera)
    """
    source = str(row.get("source", "csv")).lower()
    name   = str(row.get("name"))

    if source == "csv":
        path = str(row.get("path", "")).strip()
        if not path:
            return None
        return load_series_from_csv(path, name)

    # parquet (long local)
    if not long_df.empty:
        # Intento por descripcion == name
        df = long_df[long_df["descripcion"] == name]
        if df.empty and "id" in long_df.columns and "id" in row.index and pd.notna(row["id"]):
            df = long_df[long_df["id"] == row["id"]]
        if df.empty:
            return None
        s = pd.Series(df["valor"].values, index=pd.to_datetime(df["fecha"].values))
        s.name = name
        s = s.dropna()
        return s

    return None

# ----------------------------
# Cargar las series seleccionadas
# ----------------------------
selected_rows = cat[cat["name"].isin(sel)].copy()
loaded = {}
for _, r in selected_rows.iterrows():
    try:
        s = load_one_series(r)
        if s is not None and not s.empty:
            loaded[r["name"]] = s.sort_index()
    except Exception as e:
        st.warning(f"No pude cargar '{r.get('name','(sin nombre)')}': {e}")

if not loaded:
    st.error("No pude cargar ninguna serie de las seleccionadas. Verificá rutas/formatos en data/datosar_catalog.csv.")
    st.stop()

# Construyo WIDE por outer-join
wide = None
for name, s in loaded.items():
    if wide is None:
        wide = s.to_frame(name)
    else:
        wide = wide.join(s.to_frame(name), how="outer")
wide = wide.sort_index()

# ----------------------------
# Rango + frecuencia
# ----------------------------
dmin, dmax = wide.index.min(), wide.index.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="datosar", show_government=False)
freq = "D" if freq_label.startswith("Diaria") else "M"

vis = wide.loc[d_ini:d_fin]
if freq == "M":
    vis = vis.resample("M").last()
vis = vis.dropna(how="all")

# ----------------------------
# Gráfico
# ----------------------------
fig = go.Figure()
palette = ["#60A5FA", "#F87171", "#34D399"]

for i, name in enumerate(sel):
    if name not in vis.columns:
        continue
    s = vis[name].dropna()
    if s.empty:
        continue
    color = palette[i % len(palette)]
    fig.add_trace(
        go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=clean_label(name),
            line=dict(width=2, color=color),
            hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
        )
    )

fig.update_layout(
    template="atlas_dark", height=620,
    margin=dict(t=30, b=80, l=70, r=60),
    showlegend=True
)
fig.update_xaxes(title_text="Fecha")
fig.update_yaxes(title_text="Valor")

st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# KPIs (Último + MoM + YoY + Δ)
# ----------------------------
def kpis_for(name: str, color: str):
    if name not in wide.columns:
        return
    full = (
        wide[name]
        .dropna()
        .astype(float)
    )
    visible = resample_series(
        vis[name].dropna(),
        freq=("D" if freq_label.startswith("Diaria") else "M"),
        how="last",
    ).dropna()

    mom, yoy, d_per = compute_kpis(full, visible)
    last_val = visible.iloc[-1] if not visible.empty else None
    kpi_quad(
        title=name,
        color=color,
        last_value=last_val,
        is_percent=looks_percent(name),
        mom=mom, yoy=yoy, d_per=d_per,
        tip_last="Último dato del rango visible (con frecuencia elegida).",
        tip_mom="Variación del último dato mensual vs el mes previo.",
        tip_yoy="Variación vs mismo mes del año previo.",
        tip_per="Variación entre primer y último dato del período visible.",
    )

for idx, name in enumerate(sel):
    kpis_for(name, palette[idx % len(palette)])
