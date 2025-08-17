import streamlit as st
import pandas as pd
from bcraapi import estadisticas

st.header("Base Monetaria – API oficial BCRA 🇦🇷")

# Obtener lista de variables monetarias disponibles
variables = estadisticas.monetarias()

# Filtrar la que sea Base Monetaria
base_monetaria = variables[variables["descripcion"].str.contains("Base Monetaria", case=False)].iloc[0]
id_var = base_monetaria["idVariable"]

# Descargar los datos de Base Monetaria
df = estadisticas.monetarias(id_variable=id_var, desde="2024-01-01")

# Convertir columnas
df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True)
df["valor"] = pd.to_numeric(df["valor"].str.replace(".", "").str.replace(",", "."), errors="coerce")
df = df.dropna()

# Gráfico
st.line_chart(df.set_index("fecha")["valor"])

# Último dato como métrica
ultimo_valor = df["valor"].iloc[-1]
ultima_fecha = df["fecha"].iloc[-1].strftime("%d/%m/%Y")
st.metric("Último valor", f"${ultimo_valor:,.0f}", help=f"Fecha: {ultima_fecha}")

st.caption("Fuente: API oficial BCRA (principales variables monetarias)")
