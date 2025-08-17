import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("Dashboard Macro Argentina 🇦🇷")
st.header("Reservas Internacionales del BCRA (USD millones)")

# Leer el archivo Excel
df = pd.read_excel("reservas_bcra.xlsx", engine="openpyxl")

# Limpiar columnas
df["Fecha"] = pd.to_datetime(df["Fecha"])
df["Reservas Internacionales"] = pd.to_numeric(df["Reservas Internacionales"], errors="coerce")
df = df.dropna()

# Mostrar tabla (opcional)
st.dataframe(df)

# Gráfico de líneas
st.line_chart(df.set_index("Fecha")["Reservas Internacionales"])

st.caption("Fuente: BCRA - Carga manual")
