import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Visualizador de Excel Monetario 📊")

archivo_excel = st.file_uploader("Subí tu archivo Excel (.xlsx)", type=["xlsx"])

def detectar_fila_header(excel_path, sheet_name="DATOS | DATA"):
    temp_df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
    for i, row in temp_df.iterrows():
        row_str = row.astype(str).str.lower()
        if row_str.str.contains("date").any() or row_str.str.contains("fecha").any():
            return i  # fila donde están los encabezados
    return None

if archivo_excel:
    try:
        fila_header = detectar_fila_header(archivo_excel)
        if fila_header is None:
            st.error("No se pudo encontrar una fila con 'Date' o 'Fecha'.")
        else:
            df = pd.read_excel(archivo_excel, sheet_name="DATOS | DATA", header=fila_header)
            st.subheader("Vista previa de los datos")
            st.dataframe(df.head())

            columnas = df.columns.tolist()
            columnas_con_fecha = [col for col in columnas if "date" in str(col).lower() or "fecha" in str(col).lower()]
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
