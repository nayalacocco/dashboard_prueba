import streamlit as st

st.set_page_config(page_title="Macro AR – Panel", layout="wide", page_icon="📊")

st.title("📊 Macro Argentina – Panel principal")

st.markdown("""
Bienvenido. Elegí una fuente de datos:

- **BCRA**: Monetaria, tasas, reservas, pasivos, y comparadores.
- **MECON**: (próximamente) Inflación, actividad, finanzas públicas.
""")

c1, c2 = st.columns(2)

with c1:
    st.subheader("🇦🇷 BCRA")
    st.write("Indicadores monetarios y cambiarios (API v3, auto-actualizado).")
    st.page_link("pages/10_BCRA.py", label="Abrir módulo BCRA →", icon="📈")

with c2:
    st.subheader("🏛️ MECON")
    st.write("IPC, actividad y otras series (próximamente).")
    st.button("Abrir módulo MECON →", disabled=True)
