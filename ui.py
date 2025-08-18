# ui.py
import streamlit as st
from uuid import uuid4

# ---------- tema / toggle (como ya lo tenés) ----------
# ... deja igual get_theme(), set_theme(), theme_switcher(), plotly_template()

def inject_css():
    theme = st.session_state.get("theme", "dark")
    if theme == "dark":
        bg, bg2, txt = "#0B1220", "#111827", "#E5E7EB"
        border, card_bg, muted = "rgba(229,231,235,.25)", "rgba(255,255,255,.04)", "rgba(229,231,235,.80)"
    else:
        bg, bg2, txt = "#FFFFFF", "#F7FAFC", "#0F172A"
        border, card_bg, muted = "rgba(15,23,42,.12)", "#FFFFFF", "rgba(15,23,42,.70)"

    st.markdown(f"""
    <style>
    .stApp {{
        background: linear-gradient(180deg, {bg} 0%, {bg2} 100%) !important;
        color: {txt} !important;
    }}
    .block-container {{ padding-top: 1.1rem; padding-bottom: 2rem; }}
    #MainMenu, footer {{ visibility: hidden; }}

    h1, .stMarkdown h1 {{ font-size: 1.9rem; margin-bottom: .3rem; }}
    h2, .stMarkdown h2 {{ font-size: 1.3rem; margin-top: .8rem; margin-bottom: .2rem; }}
    h3, .stMarkdown h3 {{ font-size: 1.05rem; }}

    /* --- Tarjetas clickeables --- */
    .card {{
        width: 360px;                 /* compacto en pantallas grandes */
        max-width: 100%;
        border-radius: 16px;
        border: 1px solid {border};
        background: {card_bg};
        backdrop-filter: blur(2px);
        box-shadow: 0 4px 16px rgba(15,23,42,0.06);
        padding: 16px 18px;
        cursor: pointer;
        transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        display: flex; flex-direction: column; gap: 6px;
    }}
    .card:hover {{
        transform: translateY(-2px) scale(1.015);
        box-shadow: 0 12px 30px rgba(2,6,23,.20);
        border-color: rgba(14,165,233,.45);
    }}
    .card h3 {{ margin: 0; font-size: 1.08rem; line-height: 1.2; }}
    .muted {{ color: {muted}; font-size: 0.93rem; }}

    /* contenedor de mosaicos */
    .tiles {{ display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start; }}
    .js-plotly-plot {{ margin-bottom: 26px; }}
    </style>
    """, unsafe_allow_html=True)

def card(title: str, body_md: str, page_path: str | None = None, icon: str = "📈"):
    """
    Tarjeta con link nativo (st.page_link). Compatible con Streamlit Cloud.
    """
    cid = f"card-{uuid4().hex[:8]}"

    # marco visual de la tarjeta
    st.markdown(
        f"""
        <div class="card" id="{cid}">
          <h3>{icon} {title}</h3>
          <div class="muted">{body_md}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # si tiene página destino, muestro un link estilo botón compacto
    if page_path:
        # botón/link corto y claro
        st.page_link(
            page_path,
            label="Abrir módulo",
            icon="↗️",
        )
def kpi(label: str, value: str, help: str | None = None):
    st.markdown(f"""
    <div class="card" style="padding:12px">
      <div class="muted">{label}</div>
      <div style="font-size:1.35rem; font-weight:700; margin-top:2px">{value}</div>
    </div>
    """, unsafe_allow_html=True)
    if help: st.caption(help)
