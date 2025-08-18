import streamlit as st

st.set_page_config(page_title="BCRA – Hub", layout="wide")

st.title("🇦🇷 BCRA – Módulos principales")

c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("1) Agregados monetarios")
    st.write("Base, M1, M2, M3, circulante. Crecimientos mensual/i.a.")
    st.page_link("pages/11_BCRA_Agregados.py", label="Abrir →", icon="📈")

with c2:
    st.subheader("2) Política monetaria y tasas")
    st.write("Tasa de política, Pases, Badlar, Plazos fijos.")
    st.page_link("pages/12_BCRA_Tasas.py", label="Abrir →", icon="📉")

with c3:
    st.subheader("3) Pasivos remunerados")
    st.write("Leliqs/Pases, relación con base, absorción.")
    st.page_link("pages/13_BCRA_Pasivos.py", label="Abrir →", icon="📊")

c4, c5 = st.columns(2)
with c4:
    st.subheader("4) Reservas y tipo de cambio")
    st.write("Reservas (USD), A3500, ratios y variaciones.")
    st.page_link("pages/14_BCRA_Reservas_TC.py", label="Abrir →", icon="💱")

with c5:
    st.subheader("5) Comparador libre")
    st.write("Elegí 1 o 2 series y compará en varios modos.")
    st.page_link("pages/15_BCRA_Comparador_Libre.py", label="Abrir →", icon="🧪")
