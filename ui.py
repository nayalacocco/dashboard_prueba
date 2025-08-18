# ui.py
import streamlit as st
from uuid import uuid4

# ---------- tema / toggle (como ya lo tenés) ----------
# ... deja igual get_theme(), set_theme(), theme_switcher(), plotly_template()

def inject_css():
    theme = "dark" if st.session_state.get("theme", "dark") == "dark" else "light"
    if theme == "dark":
        bg, bg2, txt = "#0B1220", "#111827", "#E5E7EB"
        border, card_bg, muted = "rgba(229,231,235,.25)", "rgba(255,255,255,.04)", "rgba(229,231,235,.80)"
        chip_bg = "rgba(255,255,255,.06)"
    else:
        bg, bg2, txt = "#FFFFFF", "#F7FAFC", "#0F172A"
        border, card_bg, muted = "rgba(15,23,42,.12)", "#FFFFFF", "rgba(15,23,42,.70)"
        chip_bg = "#F1F5F9"

    st.markdown(f"""
    <style>
    #MainMenu, footer {{ visibility: hidden; }}
    .stApp {{
        background: linear-gradient(180deg, {bg} 0%, {bg2} 100%) !important;
        color: {txt} !important;
    }}
    /* ancho máximo del contenido para no “estirar” en pantallas grandes */
    .block-container {{
        max-width: 1200px;
        padding-top: 1.1rem; padding-bottom: 2rem;
    }}

    h1, .stMarkdown h1 {{ font-size: 1.9rem; margin-bottom: .3rem; }}
    h2, .stMarkdown h2 {{ font-size: 1.3rem; margin-top: .8rem; margin-bottom: .2rem; }}
    h3, .stMarkdown h3 {{ font-size: 1.05rem; }}

    /* GRID de mosaicos */
    .tiles {{
        display: flex; flex-wrap: wrap; gap: 20px;
        justify-content: center; align-items: stretch;
        margin-top: 10px;
    }}

    /* Tarjeta */
    .card {{
        width: 320px; max-width: 100%;
        border-radius: 14px;
        border: 1px solid {border};
        background: {card_bg};
        box-shadow: 0 4px 16px rgba(15,23,42,0.06);
        padding: 14px 16px;
        display: flex; flex-direction: column; gap: 8px;
        transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
    }}
    .card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 14px 30px rgba(2,6,23,.20);
        border-color: rgba(14,165,233,.45);
    }}
    .card h3 {{ margin: 0; font-size: 1.06rem; line-height: 1.25; }}
    .muted {{ color: {muted}; font-size: 0.93rem; }}

    /* Pie de tarjeta con el link alineado a la derecha */
    .card-footer {{
        display: flex; justify-content: flex-end; margin-top: 6px;
    }}
    /* Estilo del page_link como “chip/botón” */
    a[data-testid="stPageLink"] {{
        background: {chip_bg};
        border: 1px solid {border};
        padding: 6px 10px;
        border-radius: 10px;
        text-decoration: none;
        font-size: 0.92rem;
    }}
    a[data-testid="stPageLink"]:hover {{
        border-color: rgba(14,165,233,.55);
    }}

    .js-plotly-plot {{ margin-bottom: 26px; }}
    </style>
    """, unsafe_allow_html=True)
def card(title: str, body_md: str, page_path: str | None = None, icon: str = "📈"):
    st.markdown(
        f"""
        <div class="card">
          <h3>{icon} {title}</h3>
          <div class="muted">{body_md}</div>
          <div class="card-footer">
            {"<span></span>" if not page_path else ""}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # colocamos el link justo debajo (queda dentro del “footer” visualmente)
    if page_path:
        st.markdown('<div class="card-footer">', unsafe_allow_html=True)
        st.page_link(page_path, label="Abrir módulo", icon="↗️")
        st.markdown('</div>', unsafe_allow_html=True)
        
def kpi(label: str, value: str, help: str | None = None):
    st.markdown(f"""
    <div class="card" style="padding:12px">
      <div class="muted">{label}</div>
      <div style="font-size:1.35rem; font-weight:700; margin-top:2px">{value}</div>
    </div>
    """, unsafe_allow_html=True)
    if help: st.caption(help)
# --- ui.py (helpers de rango rápido + gobiernos) ---

import pandas as pd
from datetime import date

# períodos presidenciales (inclusive)
GOV_PERIODS = {
    "Néstor Kirchner (2003–2007)": (pd.Timestamp("2003-05-25"), pd.Timestamp("2007-12-10")),
    "Cristina Fernández I (2007–2011)": (pd.Timestamp("2007-12-10"), pd.Timestamp("2011-12-10")),
    "Cristina Fernández II (2011–2015)": (pd.Timestamp("2011-12-10"), pd.Timestamp("2015-12-10")),
    "Mauricio Macri (2015–2019)": (pd.Timestamp("2015-12-10"), pd.Timestamp("2019-12-10")),
    "Alberto Fernández (2019–2023)": (pd.Timestamp("2019-12-10"), pd.Timestamp("2023-12-10")),
    "Javier Milei (2023– )": (pd.Timestamp("2023-12-10"), pd.Timestamp(date.today())),
}

def _quick_range_bounds(min_date: pd.Timestamp, max_date: pd.Timestamp, label: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    md, MX = pd.Timestamp(min_date), pd.Timestamp(max_date)
    if label == "Máximo":
        return md, MX
    if label == "1M":
        return max(md, MX - pd.DateOffset(months=1)), MX
    if label == "3M":
        return max(md, MX - pd.DateOffset(months=3)), MX
    if label == "6M":
        return max(md, MX - pd.DateOffset(months=6)), MX
    if label == "1 año":
        return max(md, MX - pd.DateOffset(years=1)), MX
    if label == "2 años":
        return max(md, MX - pd.DateOffset(years=2)), MX
    if label == "YTD":
        start_ytd = pd.Timestamp(year=MX.year, month=1, day=1)
        return max(md, start_ytd), MX
    return md, MX

def range_controls(min_date: pd.Timestamp, max_date: pd.Timestamp, key: str = ""):
    """
    Devuelve (start, end, freq_label) según selects.
    - Frecuencia default: Diaria
    - Si se elige Gobierno, tiene prioridad sobre 'Rango rápido'
    """
    c1, c2, c3 = st.columns([1.1, 1.1, 1.0])
    with c1:
        quick = st.selectbox(
            "Rango rápido",
            ["Máximo", "1M", "3M", "6M", "1 año", "YTD", "2 años"],
            index=0, key=f"quick_{key}",
        )
    with c2:
        gov = st.selectbox(
            "Gobierno (opcional)",
            ["(ninguno)"] + list(GOV_PERIODS.keys()),
            index=0, key=f"gov_{key}",
        )
    with c3:
        freq = st.selectbox(
            "Frecuencia",
            ["Diaria", "Mensual (fin de mes)"],  # default Diaria
            index=0, key=f"freq_{key}",
        )

    # calcular rango
    if gov != "(ninguno)":
        start, end = GOV_PERIODS[gov]
        # clamp al min/max de los datos
        start = max(pd.Timestamp(min_date), start)
        end = min(pd.Timestamp(max_date), end)
    else:
        start, end = _quick_range_bounds(min_date, max_date, quick)

    return start.normalize(), end.normalize(), freq
