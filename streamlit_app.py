import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="Macro AR - BCRA", layout="wide")
st.title("📊 Macro Argentina – BCRA (API v3, auto-actualizado)")

CSV_LONG = Path("data/monetarias_long.csv")
CAT_JSON  = Path("data/monetarias_catalogo.json")

@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(CSV_LONG)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha"]).sort_values("fecha")
    return df

@st.cache_data(ttl=3600)
def load_catalog():
    return pd.read_json(CAT_JSON)

df = load_data()
cat = load_catalog()

# 🧭 Selector de variable
# Usamos el catálogo para nombres prolijos (orden alfabético)
opciones = cat["descripcion"].sort_values().tolist()
sel = st.selectbox("Seleccioná la variable a graficar", opciones, index=opciones.index("base monetaria – total (en millones de pesos)") if "base monetaria – total (en millones de pesos)" in opciones else 0)

dfv = df[df["descripcion"] == sel]

# 📅 Filtro de fechas (por defecto, serie completa)
c1, c2 = st.columns(2)
with c1:
    d_ini = st.date_input("Desde", dfv["fecha"].min().date(), min_value=dfv["fecha"].min().date(), max_value=dfv["fecha"].max().date())
with c2:
    d_fin = st.date_input("Hasta", dfv["fecha"].max().date(), min_value=dfv["fecha"].min().date(), max_value=dfv["fecha"].max().date())

mask = (dfv["fecha"] >= pd.to_datetime(d_ini)) & (dfv["fecha"] <= pd.to_datetime(d_fin))
dfv = dfv.loc[mask]

# 📈 Gráfico (sin tabla abajo)
fig = px.line(dfv, x="fecha", y="valor", title=sel, labels={"fecha": "Fecha", "valor": "Valor"})
st.plotly_chart(fig, use_container_width=True)

# (Opcional) botón de descarga del recorte
with st.expander("Descargar CSV (rango filtrado)"):
    st.download_button("Descargar", data=dfv.to_csv(index=False).encode("utf-8"), file_name="serie_filtrada.csv", mime="text/csv")
