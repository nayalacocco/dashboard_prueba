import streamlit as st
import pandas as pd
import requests

st.header("Base Monetaria – API oficial BCRA 🇦🇷 (sin wrapper)")

# Endpoint oficial
url = "https://api.bcra.gob.ar/estadisticas/v1/principalesvariables"

# GET request
try:
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
except Exception as e:
    st.error(f"Error al obtener datos: {e}")
    st.stop()

# Filtrar Base Monetaria
df = pd.DataFrame(data)
df = df[df["descripcion"].str.contains("Base Monetaria", case=False)]

# Procesar
df["fecha"] = pd.to_datetime(df["fecha"])
df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
df = df.dropna()
df = df.sort_values("fecha")

# Gráfico
st.line_chart(df.set_index("fecha")["valor"])

# Último valor
ultimo = df.iloc[-1]
st.metric("Último valor", f"${ultimo['valor']:,.0f}", help=f"Fecha: {ultimo['fecha'].strftime('%d/%m/%Y')}")

st.caption("Fuente: API oficial BCRA")
