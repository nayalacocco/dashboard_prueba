# pages/10_BCRA.py
import streamlit as st
from ui import inject_css, card

st.set_page_config(page_title="BCRA – Hub", layout="wide")
inject_css()

st.title("🇦🇷 BCRA – Módulos principales")
st.caption("Atajos a los reportes. Elegí un módulo para explorar.")

# Usamos la versión nueva de `card(title, body_md, page_path=..., icon=...)`
col1, col2, col3 = st.columns(3)
with col1:
    card(
        title="1) Agregados monetarios",
        body_md="Base, M1, M2, M3, circulante. Crecimientos mensual/i.a.",
        page_path="pages/11_BCRA_Agregados.py",
        icon="📈",
    )
with col2:
    card(
        title="2) Política monetaria y tasas",
        body_md="Tasa de política, Pases, Badlar, Plazos fijos.",
        page_path="pages/12_BCRA_Tasas.py",
        icon="📉",
    )
with col3:
    card(
        title="3) Pasivos remunerados",
        body_md="Leliqs/Pases, relación con base, absorción.",
        page_path="pages/13_BCRA_Pasivos.py",
        icon="📊",
    )

col4, col5 = st.columns(2)
with col4:
    card(
        title="4) Reservas y tipo de cambio",
        body_md="Reservas (USD), A3500, ratios y variaciones.",
        page_path="pages/14_BCRA_Reservas_TC.py",
        icon="💱",
    )
with col5:
    card(
        title="5) Comparador libre",
        body_md="Elegí 1 o 2 series y compará en varios modos.",
        page_path="pages/15_BCRA_Comparador_Libre.py",
        icon="🧪",
    )
