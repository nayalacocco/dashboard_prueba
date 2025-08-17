import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")

st.title("Dashboard de Prueba")

uploaded_file = st.file_uploader("Subí tu archivo Excel (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file, sheet_name="DATOS | DATA")
    except Exception as e:
        st.error(f"No se pudo leer la hoja 'DATOS | DATA'. Error: {e}")
        st.stop()

    df.columns = df.columns.str.strip()  # Quita espacios en blanco

    st.subheader("Vista previa de los datos")
    st.dataframe(df)

    columnas_fecha = [col for col in df.columns if "Fecha" in col]

    if not columnas_fecha:
        st.error("⚠️ No se encontró ninguna columna que contenga 'Fecha'")
        st.write("Estas son las columnas detectadas:", df.columns.tolist())
        st.stop()

    # Convertimos las columnas que contienen "Fecha" a datetime
    for col in columnas_fecha:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    columna_fecha = st.selectbox("Elegí la columna de fecha", columnas_fecha)

    columnas_numericas = df.select_dtypes(include=["number"]).columns.tolist()
    if not columnas_numericas:
        st.error("⚠️ No se encontraron columnas numéricas para graficar.")
        st.stop()

    columna_valor = st.selectbox("Elegí la variable numérica para graficar", columnas_numericas)

    st.subheader("Gráfico de línea")
    fig = px.line(df, x=columna_fecha, y=columna_valor, title="Evolución temporal")
    st.plotly_chart(fig, use_container_width=True)
