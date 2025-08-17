# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="Macro Argentina – BCRA", layout="wide")
st.title("🇦🇷 Macro Argentina – BCRA (API v3, auto-actualizado)")

CSV_LONG = Path("data/monetarias_long.csv")
CAT_JSON  = Path("data/monetarias_catalogo.json")

# -------------------- loaders con cache --------------------
@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(CSV_LONG)
    # normalizo tipos por si el fetch se actualiza
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    # sólo filas con fecha válida
    df = df.dropna(subset=["fecha"]).sort_values(["descripcion", "fecha"])
    return df

@st.cache_data(ttl=3600)
def load_catalog():
    cat = pd.read_json(CAT_JSON)
    # columnas esperadas: id, descripcion, unidad (puede venir sólo algunas)
    cat["descripcion"] = cat["descripcion"].astype(str).str.strip()
    return cat

df = load_data()
cat = load_catalog()

# Excluir del selector aquellas variables sin datos válidos en df
vars_con_datos = set(df["descripcion"].unique())
cat_filtrado = cat[cat["descripcion"].isin(vars_con_datos)].copy()
opciones = sorted(cat_filtrado["descripcion"].unique().tolist())

if not opciones:
    st.error("No hay variables con datos válidos. Verificá que existan los archivos en data/: monetarias_long.csv y monetarias_catalogo.json")
    st.stop()

# Variable por defecto: si existe Base monetaria total, usarla
default_desc = next((v for v in opciones if "base monetaria" in v.lower()), opciones[0])
sel_idx = opciones.index(default_desc) if default_desc in opciones else 0

# -------------------- UI: selector y rango de fechas --------------------
sel = st.selectbox("Seleccioná la variable a graficar", opciones, index=sel_idx)

# Filtrar la variable seleccionada
dfv = df[df["descripcion"] == sel].copy()

# Normalizar y validar fechas
dfv["fecha"] = pd.to_datetime(dfv["fecha"], errors="coerce")
dfv = dfv.dropna(subset=["fecha"]).sort_values("fecha")

# Si la serie está vacía, no crashear
if dfv.empty:
    st.warning("No hay datos con fechas válidas para esta variable.")
    st.stop()

# Fechas seguras para los widgets
fmin = dfv["fecha"].min().date()
fmax = dfv["fecha"].max().date()

c1, c2 = st.columns(2)
with c1:
    d_ini = st.date_input("Desde", value=fmin, min_value=fmin, max_value=fmax)
with c2:
    d_fin = st.date_input("Hasta", value=fmax, min_value=fmin, max_value=fmax)

# Asegurar orden si el usuario invierte el rango
if pd.to_datetime(d_ini) > pd.to_datetime(d_fin):
    d_ini, d_fin = d_fin, d_ini

mask = (dfv["fecha"] >= pd.to_datetime(d_ini)) & (dfv["fecha"] <= pd.to_datetime(d_fin))
dfv = dfv.loc[mask]

# Si el filtro dejó vacío, aviso amigable
if dfv.empty:
    st.info("No hay observaciones en el rango elegido.")
    st.stop()

# -------------------- gráfico --------------------
fig = px.line(
    dfv,
    x="fecha",
    y="valor",
    title=sel,
    labels={"fecha": "Fecha", "valor": "Valor"}
)
st.plotly_chart(fig, use_container_width=True)

# Métrica del último dato visible
last = dfv.iloc[-1]
st.metric("Último dato visible", f"{last['valor']:,.0f}", help=f"Fecha: {last['fecha'].date()}")

# (Opcional) descarga del recorte
with st.expander("Descargar CSV (rango filtrado)"):
    st.download_button(
        "Descargar",
        data=dfv.to_csv(index=False).encode("utf-8"),
        file_name="serie_filtrada.csv",
        mime="text/csv",
    )
