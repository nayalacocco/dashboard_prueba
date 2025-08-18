import streamlit as st
from ui import inject_css, card, theme_switcher

st.set_page_config(page_title="Macro AR – Panel", layout="wide", page_icon="📊")
inject_css()
theme_switcher(location="sidebar")

st.title("📊 Macro Argentina – Panel principal")
st.caption("Navegá por módulos. Los datos del BCRA se actualizan automáticamente desde el repo.")

st.markdown('<div class="tiles">', unsafe_allow_html=True)

card(
    title="BCRA",
    body_md="Indicadores monetarios y cambiarios (API v3, auto-actualizado).",
    page_path="pages/10_BCRA.py",
    icon="🇦🇷",
)

card(
    title="MECON (Próximamente)",
    body_md="IPC, actividad y finanzas públicas.",
    page_path=None,
    icon="🏛️",
)

st.markdown('</div>', unsafe_allow_html=True)
