import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("Dashboard Macro Argentina 🇦🇷")
st.header("Reservas Internacionales del BCRA (USD millones)")

# Leer Excel (requiere openpyxl, ya está incluido en Streamlit Cloud)
df = pd.read_excel("reservas_bcra.xlsx", engine="openpyxl", parse_dates=["fecha"])

# Mostrar tabla
st.dataframe(df)

# Mostrar gráfico
st.line_chart(df.set_index("fecha")["reservas_usd"])

st.caption("Fuente: Carga manual desde Excel - BCRA")
