import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="Base Monetaria BCRA", layout="wide")

st.title("📊 Visualizador de la Base Monetaria (BCRA)")

DATA_PATH = Path("data/base_monetaria.csv")

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna().sort_values("fecha")
    return df

df = load_data()

st.write(f"**Datos disponibles:** {len(df)} observaciones, desde {df['fecha'].min().date()} hasta {df['fecha'].max().date()}")

# Selector de rango de fechas
min_date, max_date = df["fecha"].min(), df["fecha"].max()
rango = st.date_input(
    "Filtrar por rango de fechas:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if len(rango) == 2:
    df = df[(df["fecha"] >= pd.to_datetime(rango[0])) & (df["fecha"] <= pd.to_datetime(rango[1]))]

# Gráfico
fig = px.line(df, x="fecha", y="valor", title="Evolución de la Base Monetaria (millones de $)", labels={
    "fecha": "Fecha",
    "valor": "Valor"
})
st.plotly_chart(fig, use_container_width=True)

# Tabla
st.dataframe(df.tail(20))
