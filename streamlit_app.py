import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Visualizador de Excel Monetario 📊")

# Subida del archivo
archivo_excel = st.file_uploader("Subí tu archivo Excel (.xlsx)", type=["xlsx"])

if archivo_excel:
    try:
        # LEER desde la hoja "DATOS | DATA" y SALTEAR las primeras 5 filas
        df = pd.read_excel(archivo_excel, sheet_name="DATOS | DATA", skiprows=5)

        st.subheader("Vista previa de los datos")
        st.dataframe(df.head())

        columnas = df.columns.tolist()
        columnas_con_fecha = [col for col in columnas if "date" in col.lower() or "fecha" in col.lower()]
        columnas_numericas = df.select_dtypes(include=["number"]).columns.tolist()

        if columnas_con_fecha:
            col_fecha = st.selectbox("Seleccioná la columna de fecha", columnas_con_fecha)
            col_valor = st.selectbox("Seleccioná la columna numérica a graficar", columnas_numericas)

            df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")
            df_filtrado = df.dropna(subset=[col_fecha, col_valor])

            fig = px.line(df_filtrado, x=col_fecha, y=col_valor, title=f"{col_valor} a lo largo del tiempo")
            st.plotly_chart(fig)
        else:
            st.warning("⚠️ No se encontró ninguna columna que contenga 'Fecha' o 'Date'.")

        st.write("Estas son las columnas detectadas:")
        st.json(columnas)

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
