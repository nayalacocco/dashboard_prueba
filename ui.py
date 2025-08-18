# ui.py
import streamlit as st

# ---------- Estado y controles de tema ----------

_DEF_THEME = "dark"  # default si el user nunca eligió

def get_theme() -> str:
    # Guarda el tema en session_state; si no existe, arranca en dark
    if "theme" not in st.session_state:
        st.session_state["theme"] = _DEF_THEME
    return st.session_state["theme"]

def set_theme(new_theme: str):
    st.session_state["theme"] = "dark" if new_theme.lower() == "dark" else "light"
    st.rerun()

def theme_switcher(location: str = "sidebar"):
    """Toggle Light/Dark (simulado)"""
    theme = get_theme()
    container = st.sidebar if location == "sidebar" else st
    with container:
        toggled = st.toggle("🌗 Modo oscuro", value=(theme == "dark"),
                            help="Cambiá entre Dark y Light")
        # Si el toggle y el estado difieren, cambiamos
        if toggled and theme != "dark":
            set_theme("dark")
        elif not toggled and theme != "light":
            set_theme("light")

# ---------- Inyección de estilos ----------

def inject_css():
    theme = get_theme()
    if theme == "dark":
        bg = "#0B1220"
        bg2 = "#111827"
        txt = "#E5E7EB"
        border = "rgba(229,231,235,.25)"
        card_bg = "rgba(255,255,255,.04)"
    else:
        bg = "#FFFFFF"
        bg2 = "#F7FAFC"
        txt = "#0F172A"
        border = "rgba(15,23,42,.12)"
        card_bg = "#FFFFFF"

    st.markdown(f"""
    <style>
    /* fondo y tipografía base */
    .stApp {{
        background: linear-gradient(180deg, {bg} 0%, {bg2} 100%) !important;
        color: {txt} !important;
    }}
    .block-container {{ padding-top: 1.1rem; padding-bottom: 2rem; }}
    #MainMenu, footer {{ visibility: hidden; }}

    /* títulos */
    h1, .stMarkdown h1 {{ font-size: 1.9rem; margin-bottom: .3rem; }}
    h2, .stMarkdown h2 {{ font-size: 1.3rem; margin-top: .8rem; margin-bottom: .2rem; }}
    h3, .stMarkdown h3 {{ font-size: 1.05rem; }}

    /* cards */
    .card {{
        border-radius: 16px;
        border: 1px solid {border};
        background: {card_bg};
        backdrop-filter: blur(2px);
        box-shadow: 0 4px 16px rgba(15,23,42,0.06);
        padding: 16px 18px;
        height: 100%;
    }}
    .card h3 {{ margin: 0 0 6px 0; font-size: 1.05rem; }}
    .muted {{ opacity: .85; font-size: 0.92rem; }}

    /* sidebar */
    section[data-testid="stSidebar"] .block-container {{ padding-top: .8rem; }}
    .side-section-title {{
        font-weight: 700; font-size: .9rem; letter-spacing:.02em; margin: 6px 0 2px 0;
        text-transform: uppercase; opacity: .8;
    }}

    .js-plotly-plot {{ margin-bottom: 26px; }}
    </style>
    """, unsafe_allow_html=True)

# ---------- Helpers de UI ----------

def card(title: str, body_md: str, button_label: str | None = None,
         page_path: str | None = None, icon: str = "➡️"):
    st.markdown(f"""
    <div class="card">
      <h3>{title}</h3>
      <div class="muted">{body_md}</div>
    </div>
    """, unsafe_allow_html=True)
    if button_label and page_path:
        st.page_link(page_path, label=button_label, icon=icon)

def kpi(label: str, value: str, help: str | None = None):
    st.markdown(f"""
    <div class="card" style="padding:12px">
      <div class="muted">{label}</div>
      <div style="font-size:1.35rem; font-weight:700; margin-top:2px">{value}</div>
    </div>
    """, unsafe_allow_html=True)
    if help: st.caption(help)

# ---------- Plotly: template según tema ----------

def plotly_template() -> str:
    """Devolvé 'plotly_dark' o 'plotly_white' según el tema actual."""
    return "plotly_dark" if get_theme() == "dark" else "plotly_white"
