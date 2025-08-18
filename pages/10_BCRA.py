import streamlit as st
from ui import inject_css, card

st.set_page_config(page_title="BCRA – Hub", layout="wide")
inject_css()

st.title("🇦🇷 BCRA – Módulos principales")
st.caption("Atajos a los reportes. Elegí un módulo para explorar.")

c1, c2, c3 = st.columns(3)
with c1:
    card("1) Agregados monetarios", "Base, M1, M2, M3, circulante. Crecimientos mensual/i.a.",
         "Abrir →", "pages/11_BCRA_Agregados.py", "📈")
with c2:
    card("2) Política monetaria y tasas", "Tasa de política, Pases, Badlar, Plazos fijos.",
         "Abrir →", "pages/12_BCRA_Tasas.py", "📉")
with c3:
    card("3) Pasivos remunerados", "Leliqs/Pases, relación con base, absorción.",
         "Abrir →", "pages/13_BCRA_Pasivos.py", "📊")

c4, c5 = st.columns(2)
with c4:
    card("4) Reservas y tipo de cambio", "Reservas (USD), A3500, ratios y variaciones.",
         "Abrir →", "pages/14_BCRA_Reservas_TC.py", "💱")
with c5:
    card("5) Comparador libre", "Elegí 1 o 2 series y compará en varios modos.",
         "Abrir →", "pages/15_BCRA_Comparador_Libre.py", "🧪")
