import streamlit as st
import pandas as pd

st.set_page_config(page_title="Base Monetaria (BCRA)", layout="wide")
st.title("Base Monetaria – BCRA (datos oficiales, auto-actualizado)")

# Cambiá <USER> y <REPO> por los tuyos
RAW = "https://raw.githubusercontent.com/<USER>/<REPO>/main/data/base_monetaria.json"

@st.cache_data(ttl=3600)
def load():
    df = pd.read_json(RAW)
    # normalización por si vienen strings
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True).dt.tz_localize(None)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna().sort_values("fecha")
    return df

df = load()

# Filtro de fechas (opcional; por defecto toda la serie)
c1, c2 = st.columns(2)
with c1:
    start = st.date_input("Desde", value=df["fecha"].min().date(), min_value=df["fecha"].min().date(), max_value=df["fecha"].max().date())
with c2:
    end = st.date_input("Hasta", value=df["fecha"].max().date(), min_value=df["fecha"].min().date(), max_value=df["fecha"].max().date())

mask = (df["fecha"] >= pd.to_datetime(start)) & (df["fecha"] <= pd.to_datetime(end))
dfv = df.loc[mask]

st.line_chart(dfv.set_index("fecha")["valor"])
st.metric("Último dato", f"{df.iloc[-1]['valor']:,.0f}", help=f"Fecha: {df.iloc[-1]['fecha'].date()}")

st.caption("Fuente: API oficial BCRA (cosechada por GitHub Actions).")
