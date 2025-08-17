import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("Dashboard Macro Argentina 🇦🇷")
st.header("Reservas Internacionales del BCRA (USD millones)")

# Leer Excel y convertir columna 'Fecha' a datetime
df = pd.read_excel("reservas_bcra.xlsx", engine="openpyxl")
df["Fecha"] = pd.to_datetime(df["Fecha"])

# Mostrar tabla
st.dataframe(df)

# Mostrar gráfico (usamos 'Fecha' como índice y 'Reservas Internacionales' como serie)
st.line_chart(df.set_index("Fecha")["Reservas Internacionales"])

st.caption("Fuente: BCRA - Carga manual")
