# ui.py
from __future__ import annotations
import datetime as dt
from typing import Tuple, Optional

import plotly.io as pio
import streamlit as st

# -------------------------------------------------------------------
# Plotly template (paleta Atlas)
# -------------------------------------------------------------------
_ATLAS_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor="#0A0E1A",
        plot_bgcolor="#0A0E1A",
        font=dict(color="#FFFFFF", family="Inter, system-ui, -apple-system, Segoe UI, Roboto"),
        colorway=["#2563EB", "#34D399", "#3B82F6", "#F59E0B", "#EC4899"],
        xaxis=dict(
            gridcolor="#1F2937",
            zeroline=False,
            linecolor="#E5E7EB",
            ticks="outside",
            tickcolor="#E5E7EB",
        ),
        yaxis=dict(
            gridcolor="#1F2937",
            zeroline=False,
            linecolor="#E5E7EB",
            ticks="outside",
            tickcolor="#E5E7EB",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            orientation="h",
            y=-0.2,
            x=0.5,
            xanchor="center",
        ),
        margin=dict(t=30, r=60, b=80, l=70),
    )
)
pio.templates["atlas_dark"] = _ATLAS_TEMPLATE
pio.templates.default = "atlas_dark"


# -------------------------------------------------------------------
# CSS global (branding Atlas + mosaicos + fixes)
# -------------------------------------------------------------------
def inject_css() -> None:
    st.markdown(
        """
        <style>
        /* Ocultar menú y footer */
        #MainMenu, footer { visibility: hidden; }

        /* Fondo general + tipografía */
        .stApp {
            background-color: #0A0E1A;
            color: #FFFFFF;
        }
        .block-container {
            max-width: 1200px;
            padding-top: 1.1rem;
            padding-bottom: 2rem;
        }

        /* Headers */
        h1, h2, h3, h4 { color: #FFFFFF; }
        h1, .stMarkdown h1 { font-size: 1.9rem; margin-bottom: .3rem; }
        h2, .stMarkdown h2 { font-size: 1.3rem; margin-top: .8rem; margin-bottom: .2rem; }
        h3, .stMarkdown h3 { font-size: 1.05rem; }

        /* Texto secundario */
        .stMarkdown, label, .stSelectbox, .stMultiSelect, .stRadio, .stSlider {
            color: #9CA3AF !important;
        }

        /* Botones */
        .stButton>button {
            background: linear-gradient(90deg, #0D1B52, #2563EB);
            color: white;
            border-radius: 8px;
            border: none;
        }
        .stButton>button:hover {
            background: linear-gradient(90deg, #2563EB, #3B82F6);
        }

        /* Inputs */
        .stSelectbox, .stMultiSelect, .stTextInput, .stDateInput, .stNumberInput, .stSlider {
            background-color: #111827 !important;
            border-radius: 8px !important;
            color: #FFFFFF !important;
        }

        /* GRID de mosaicos (home) */
        .tiles {
            display: flex; flex-wrap: wrap; gap: 20px;
            justify-content: center; align-items: stretch;
            margin-top: 10px;
        }

        /* Tarjeta */
        .card {
            width: 320px; max-width: 100%;
            border-radius: 14px;
            border: 1px solid #1F2937;
            background: #111827;
            box-shadow: 0 4px 16px rgba(15,23,42,0.06);
            padding: 14px 16px;
            display: flex; flex-direction: column; gap: 8px;
            transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        }
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 14px 30px rgba(2,6,23,.20);
            border-color: rgba(37,99,235,.45);
        }
        .card h3 { margin: 0; font-size: 1.06rem; line-height: 1.25; }
        .muted { color: #9CA3AF; font-size: 0.93rem; }

        /* Pie de tarjeta con link */
        .card-footer { display: flex; justify-content: flex-end; margin-top: 6px; }
        a[data-testid="stPageLink"] {
            background: #111827;
            border: 1px solid #1F2937;
            padding: 6px 10px;
            border-radius: 10px;
            text-decoration: none;
            font-size: 0.92rem;
            color: #FFFFFF;
        }
        a[data-testid="stPageLink"]:hover {
            border-color: rgba(37,99,235,.55);
        }

        /* Plotly margin fix */
        .js-plotly-plot { margin-bottom: 26px; }

        /* ---------------------- KPIs ---------------------- */
        .kpi-box{
          background:#111827;
          border:1px solid #1F2937;
          border-radius:12px;
          padding:14px 16px;
        }
        .kpi-head{
          display:flex; align-items:center; justify-content:space-between;
          margin-bottom:6px;
        }
        .kpi-title{ color:#9CA3AF; font-size:.9rem; }
        .kpi-value{ color:#FFFFFF; font-size:1.6rem; font-weight:600; }

        /* “?” con tooltip CSS (sin el help= de Streamlit) */
        .kpi-help{
          position:relative;
          display:inline-flex; align-items:center; justify-content:center;
          width:18px; height:18px; border-radius:50%;
          border:1px solid #374151; color:#9CA3AF;
          font-size:.8rem; font-weight:700; cursor:help; user-select:none;
        }
        .kpi-help:hover::after{
          content: attr(data-tip);
          position:absolute; left:50%; transform:translateX(-50%); bottom:130%;
          background:#0B1222; color:#E5E7EB; border:1px solid #374151;
          border-radius:8px; padding:8px 10px; width:max-content; max-width:320px;
          white-space:normal; font-size:.85rem; line-height:1.2rem;
          box-shadow:0 8px 20px rgba(0,0,0,.25); z-index:9999;
        }
        .kpi-help:hover::before{
          content:""; position:absolute; left:50%; transform:translateX(-50%); bottom:118%;
          border:6px solid transparent; border-top-color:#374151;
        }
        /* --------------------------------------------------- */
        </style>
        """,
        unsafe_allow_html=True,
    )


# -------------------------------------------------------------------
# Tarjeta de la home
# -------------------------------------------------------------------
def card(title: str, body_md: str, page_path: Optional[str], icon: str = "📊") -> None:
    st.markdown(
        f"""
        <div class="card">
            <h3>{icon} {title}</h3>
            <div class="muted">{body_md}</div>
            <div class="card-footer">
        """,
        unsafe_allow_html=True,
    )
    if page_path:
        st.page_link(page_path, label="Abrir módulo", icon="📈")
    else:
        st.page_link("streamlit_app.py", label="Próximamente", disabled=True, icon="⏳")
    st.markdown("</div></div>", unsafe_allow_html=True)


# -------------------------------------------------------------------
# Controles de rango + gobierno + frecuencia
#   - Devuelve: (d_ini, d_fin, freq_label)
#   - Si se elige un gobierno (!= ninguno), tiene prioridad sobre el rango rápido
# -------------------------------------------------------------------
_GOV_PERIODS = [
    ("(ninguno)", None, None),
    ("Néstor Kirchner (2003–2007)", "2003-05-25", "2007-12-10"),
    ("Cristina Fernández I (2007–2011)", "2007-12-10", "2011-12-10"),
    ("Cristina Fernández II (2011–2015)", "2011-12-10", "2015-12-10"),
    ("Mauricio Macri (2015–2019)", "2015-12-10", "2019-12-10"),
    ("Alberto Fernández (2019–2023)", "2019-12-10", "2023-12-10"),
    ("Javier Milei (2023– )", "2023-12-10", None),
]

def _parse_date(s: Optional[str]) -> Optional[dt.date]:
    if not s:
        return None
    return dt.date.fromisoformat(s)

def range_controls(
    dmin: dt.date | dt.datetime,
    dmax: dt.date | dt.datetime,
    key: str = "",
    show_government: bool = True,
    priority: str = "gobierno",   # "gobierno" (default) o "rango"
) -> Tuple[dt.date, dt.date, str]:
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col1:
        rango = st.selectbox(
            "Rango rápido",
            ["1 mes", "3 meses", "6 meses", "1 año", "YTD", "2 años", "Máximo"],
            index=6,
            key=f"rr_{key}",
        )
    with col2:
        gov_label = "(ninguno)"
        if show_government:
            gov_label = st.selectbox(
                "Gobierno (opcional)",
                [g[0] for g in _GOV_PERIODS],
                index=0,
                key=f"gov_{key}",
            )
    with col3:
        freq_label = st.selectbox(
            "Frecuencia",
            ["Diaria", "Mensual (fin de mes)"],
            index=0,
            key=f"fq_{key}",
        )

    # fechas base
    dmin = (dmin.date() if hasattr(dmin, "date") else dmin)
    dmax = (dmax.date() if hasattr(dmax, "date") else dmax)

    # helper rango rápido
    def _range_from_quick():
        today = dmax
        if rango == "1 mes":
            d_ini = max(dmin, today - dt.timedelta(days=31))
        elif rango == "3 meses":
            d_ini = max(dmin, today - dt.timedelta(days=92))
        elif rango == "6 meses":
            d_ini = max(dmin, today - dt.timedelta(days=183))
        elif rango == "1 año":
            d_ini = max(dmin, today - dt.timedelta(days=365))
        elif rango == "YTD":
            d_ini = dt.date(today.year, 1, 1)
        elif rango == "2 años":
            d_ini = max(dmin, today - dt.timedelta(days=365 * 2))
        else:  # Máximo
            d_ini = dmin
        d_fin = dmax
        return d_ini, d_fin

    # lógica de prioridad
    if priority == "rango":
        # si el usuario eligió cualquier rango (incluido Máximo / YTD), priorizamos rango
        d_ini, d_fin = _range_from_quick()
        return d_ini, d_fin, freq_label

    # prioridad "gobierno" (comportamiento original)
    if show_government and gov_label != "(ninguno)":
        _, gini, gfin = next(g for g in _GOV_PERIODS if g[0] == gov_label)
        gini_d = _parse_date(gini) or dmin
        gfin_d = _parse_date(gfin) or dmax
        d_ini, d_fin = max(dmin, gini_d), min(dmax, gfin_d)
        return d_ini, d_fin, freq_label

    d_ini, d_fin = _range_from_quick()
    return d_ini, d_fin, freq_label


# -------------------------------------------------------------------
# KPI con tooltip (CSS) – sin usar help= para evitar la "X"
# -------------------------------------------------------------------
def kpi(title: str, value: str, help_text: Optional[str] = None) -> None:
    tip = f' data-tip="{help_text}"' if help_text else ""
    help_html = f'<div class="kpi-help"{tip}>?</div>' if help_text else ""
    html = f"""
    <div class="kpi-box">
      <div class="kpi-head">
        <div class="kpi-title">{title}</div>
        {help_html}
      </div>
      <div class="kpi-value">{value}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
