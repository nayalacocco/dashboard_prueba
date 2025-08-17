import streamlit as st
import pandas as pd
import plotly.express as px

# Cargar el archivo Excel
@st.cache_data
def cargar_datos():
    df_raw = pd.read_excel("infomondia.xlsx", sheet_name="DATOS | DATA", header=None)

    # Encabezados en filas específicas
    lvl1 = df_raw.iloc[17].fillna(method="ffill")
    lvl2 = df_raw.iloc[19].fillna(method="ffill")
    lvl3 = df_raw.iloc[25].fillna("")
    columnas = lvl1 + " | " + lvl2 + " | " + lvl3

    df = df_raw.iloc[27:].copy()
    df.columns = columnas
    df = df.reset_index(drop=True)

    return df

df = cargar_datos()

# Extraer columnas que sean fechas
columnas_fecha = [col for col in df.columns if "Fecha" in col]

# Relacionar fechas con sus variables
series_disponibles = []
for col in df.columns:
    if "Fecha" not in col and "|" in col:
        bloque = col.split(" | ")[0]
        nombre = col.split(" | ")[1]
        codigo = col.split(" | ")[2]
        series_disponibles.append({
            "etiqueta": f"{bloque} - {nombre} ({codigo})",
            "columna_valor": col,
        })

# Sidebar de selección
st.sidebar.title("📊 Selección de serie")
serie_sel = st.sidebar.selectbox("Elegí una variable", [s["etiqueta"] for s in series_disponibles])

# Buscar la columna asociada
col_valor = next(s["columna_valor"] for s in series_disponibles if s["etiqueta"] == serie_sel)

# Inferir la columna de fecha
bloque = col_valor.split(" | ")[0]
col_fecha = next((col for col in columnas_fecha if bloque in col), None)

# Limpiar y convertir fechas y valores
df = df[[col_fecha, col_valor]].dropna()
df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
df[col_valor] = pd.to_numeric(df[col_valor], errors='coerce')
df = df.dropna()

# Rango de fechas para filtrar
fecha_min, fecha_max = df[col_fecha].min(), df[col_fecha].max()
rango_fechas = st.sidebar.date_input("Filtrar fechas", [fecha_min, fecha_max])

# Aplicar filtro si se elige rango distinto
if len(rango_fechas) == 2:
    df = df[(df[col_fecha] >= pd.to_datetime(rango_fechas[0])) & (df[col_fecha] <= pd.to_datetime(rango_fechas[1]))]

# Gráfico
st.title("Evolución de la Serie Seleccionada")
fig = px.line(df, x=col_fecha, y=col_valor, title=serie_sel)
fig.update_layout(xaxis_title="Fecha", yaxis_title="Valor", height=500)
st.plotly_chart(fig, use_container_width=True)

# Mostrar tabla opcional
with st.expander("🔍 Ver datos en tabla"):
    st.dataframe(df, use_container_width=True)
