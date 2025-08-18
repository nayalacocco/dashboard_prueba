# ui.py
import streamlit as st

def inject_css():
    # estilos neutrales (sirven en light y dark)
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .block-container {padding-top: 1.1rem; padding-bottom: 2rem;}

    h1, .stMarkdown h1 {font-size: 1.9rem; margin-bottom: .3rem;}
    h2, .stMarkdown h2 {font-size: 1.3rem; margin-top: 0.8rem; margin-bottom: .2rem;}
    h3, .stMarkdown h3 {font-size: 1.05rem;}

    .card {
        border-radius: 16px;
        border: 1px solid rgba(229,231,235,.35);
        background: rgba(255,255,255,.04);
        backdrop-filter: blur(2px);
        box-shadow: 0 4px 16px rgba(15,23,42,0.05);
        padding: 16px 18px;
        height: 100%;
    }
    .card h3 { margin: 0 0 6px 0; font-size: 1.05rem;}
    .muted { opacity: .85; font-size: 0.92rem; }

    section[data-testid="stSidebar"] .block-container { padding-top: .8rem; }
    .side-section-title {
        font-weight: 700; font-size: .9rem; letter-spacing:.02em; margin: 6px 0 2px 0;
        text-transform: uppercase; opacity: .8;
    }

    .js-plotly-plot {margin-bottom: 26px;}
    </style>
    """, unsafe_allow_html=True)

def theme_switcher(location: str = "sidebar"):
    """
    Switch Light/Dark vía query param ?theme=light|dark
    - Default: dark si no hay preferencia previa
    - location: 'sidebar' o 'header'
    """
    # Leer tema actual desde query param (si no hay, asumimos 'dark')
    current = None
    try:
        # Streamlit >= 1.30
        current = st.query_params.get("theme", ["dark"])
        current = current[0] if isinstance(current, list) else current
    except Exception:
        # Compatibilidad
        current = st.experimental_get_query_params().get("theme", ["dark"])[0]

    is_dark = (current or "dark").lower() == "dark"

    def set_theme(new_theme: str):
        # Actualizar query param y forzar rerun
        try:
            qp = dict(st.query_params)
            qp["theme"] = new_theme
            st.query_params.clear()
            st.query_params.update(qp)
        except Exception:
            st.experimental_set_query_params(**{"theme": new_theme})
        st.rerun()

    container = st.sidebar if location == "sidebar" else st
    with container:
        label = "🌗 Modo oscuro"
        toggled = st.toggle(label, value=is_dark, help="Cambiá entre Dark y Light")
        if toggled and not is_dark:
            set_theme("dark")
        elif (not toggled) and is_dark:
            set_theme("light")

def card(title: str, body_md: str, button_label: str | None = None, page_path: str | None = None, icon: str = "➡️"):
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
