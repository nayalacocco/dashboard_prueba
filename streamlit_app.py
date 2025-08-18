import os, sys
import streamlit as st

# --- Import robusto para ui.py ---
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

try:
    from ui import inject_css, card
except Exception:
    import ui
    inject_css = ui.inject_css
    card = ui.card
# ----------------------------------

st.set_page_config(page_title="Macro AR – Panel", layout="wide", page_icon="📊")
inject_css()

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
