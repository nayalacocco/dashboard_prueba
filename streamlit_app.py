import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Subida del archivo .xlsx
uploaded_file = st.file_uploader("Subí el archivo Excel", type="xlsx")

if uploaded_file is not None:
    # Leer hoja específica
    try:
        df = pd.read_excel(uploaded_file, sheet_name="DATOS | DATA")
    except ValueError as e:
        st.error(f"No se pudo encontrar la hoja 'DATOS | DATA': {e}")
        st.stop()

    # Normalizar nombres de columnas
    df.columns = df.columns.str.strip()

    # Detectar columnas que contengan "Fecha"
    columnas_fecha = [col for col in df.columns if "Fecha" in col]

    if not columnas_fecha:
        st.error("No se encontró ninguna columna con la palabra 'Fecha'")
        st.write("Columnas disponibles:", df.columns.tolist())
        st.stop()

    col_fecha = columnas_fecha[0]
    df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")
    df = df.dropna(subset=[col_fecha])

    # Elegir variable a graficar
    columnas_numericas = df.select_dtypes(include='number').columns.tolist()
    if not columnas_numericas:
        st.error("No hay columnas numéricas para graficar.")
        st.stop()

    variable = st.selectbox("Seleccioná la variable a graficar", columnas_numericas)

    # Elegir rango de fechas
    min_fecha = df[col_fecha].min().date()
    max_fecha = df[col_fecha].max().date()

    start_date, end_date = st.date_input("Rango de fechas", [min_fecha, max_fecha], min_value=min_fecha, max_value=max_fecha)

    # Filtrar DataFrame por rango
    mask = (df[col_fecha] >= pd.to_datetime(start_date)) & (df[col_fecha] <= pd.to_datetime(end_date))
    df_filtrado = df.loc[mask]

    # Gráfico
    fig, ax = plt.subplots()
    ax.plot(df_filtrado[col_fecha], df_filtrado[variable])
    ax.set_xlabel("Fecha")
    ax.set_ylabel(variable)
    ax.set_title(f"{variable} a lo largo del tiempo")
    st.pyplot(fig)
