# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Base Monetaria – BCRA", layout="wide")
st.title("Base Monetaria – BCRA (API oficial, auto-actualizado)")

RAW_URL = "https://raw.githubusercontent.com/nayalacocco/dashboard_prueba/main/data/base_monetaria.csv"

@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(RAW_URL)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True).dt.tz_localize(None)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna().sort_values("fecha")
    return df

df = load_data()

# Filtro de fechas (por default: toda la serie)
c1, c2 = st.columns(2)
with c1:
    d_ini = st.date_input("Desde", value=df["fecha"].min().date(), min_value=df["fecha"].min().date(), max_value=df["fecha"].max().date())
with c2:
    d_fin = st.date_input("Hasta", value=df["fecha"].max().date(), min_value=df["fecha"].min().date(), max_value=df["fecha"].max().date())

mask = (df["fecha"] >= pd.to_datetime(d_ini)) & (df["fecha"] <= pd.to_datetime(d_fin))
dff = df.loc[mask]

fig = px.line(dff, x="fecha", y="valor", title="Evolución de la Base Monetaria (millones)")
st.plotly_chart(fig, use_container_width=True)

if not dff.empty:
    ultimo = dff.iloc[-1]
    st.metric("Último dato", f"{ultimo['valor']:,.0f}", help=f"Fecha: {ultimo['fecha'].date()}")

with st.expander("Ver datos"):
    st.dataframe(dff, use_container_width=True)
