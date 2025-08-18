import streamlit as st
from ui import inject_css, card

st.set_page_config(page_title="Macro AR – Panel", layout="wide", page_icon="📊")
inject_css()

st.title("📊 Macro Argentina – Panel principal")
st.caption("Navegá por módulos. Los datos del BCRA se actualizan automáticamente desde el repo.")

c1, c2 = st.columns(2)
with c1:
    card(
        "🇦🇷 BCRA",
        "Indicadores monetarios y cambiarios (API v3, auto-actualizado).",
        button_label="Abrir módulo BCRA",
        page_path="pages/10_BCRA.py",
        icon="📈",
    )

with c2:
    card(
        "🏛️ MECON (Próximamente)",
        "IPC, actividad y finanzas públicas.",
        button_label=None, page_path=None
    )
