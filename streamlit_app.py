import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(layout="wide", page_title="Visualizador Económico")

# Carga de datos
@st.cache_data
def cargar_datos():
    df = pd.read_excel("infomondia.xlsx", sheet_name="DATOS | DATA")
    df.columns = df.columns.str.strip()  # limpia espacios en nombres de columnas
    df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0], errors='coerce')  # convierte primera columna a datetime
    return df.dropna(subset=[df.columns[0]])  # descarta filas sin fecha

df = cargar_datos()
columna_fecha = df.columns[0]
columnas_disponibles = df.columns[1:]

# Sidebar: selección de variable y fechas
st.sidebar.header("Parámetros")
variable = st.sidebar.selectbox("Seleccioná la variable a graficar", columnas_disponibles)

fecha_min = df[columna_fecha].min()
fecha_max = df[columna_fecha].max()

rango_fecha = st.sidebar.date_input(
    "Filtrar por rango de fechas (opcional)",
    value=(fecha_min, fecha_max),
    min_value=fecha_min,
    max_value=fecha_max
)

# Filtro de fechas
if isinstance(rango_fecha, tuple):
    fecha_inicio, fecha_fin = rango_fecha
else:
    fecha_inicio = fecha_min
    fecha_fin = fecha_max

df_filtrado = df[(df[columna_fecha] >= pd.to_datetime(fecha_inicio)) & (df[columna_fecha] <= pd.to_datetime(fecha_fin))]

# Gráfico
st.title("Visualizador de Series Económicas")
st.subheader(f"Variable seleccionada: {variable}")

fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(df_filtrado[columna_fecha], df_filtrado[variable], marker='o', linestyle='-')
ax.set_xlabel("Fecha")
ax.set_ylabel(variable)
ax.grid(True)

st.pyplot(fig)
