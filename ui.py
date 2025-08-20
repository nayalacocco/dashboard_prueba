# ui.py
from __future__ import annotations
import datetime as dt
from typing import Tuple, Optional

import plotly.io as pio
import streamlit as st

# ---------------- Plotly template (paleta Atlas) ----------------
_ATLAS_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor="#0A0E1A",
        plot_bgcolor="#0A0E1A",
        font=dict(color="#FFFFFF", family="Inter, system-ui, -apple-system, Segoe UI, Roboto"),
        colorway=["#2563EB", "#34D399", "#3B82F6", "#F59E0B", "#EC4899"],
        xaxis=dict(gridcolor="#1F2937", zeroline=False, linecolor="#E5E7EB", ticks="outside", tickcolor="#E5E7EB"),
        yaxis=dict(gridcolor="#1F2937", zeroline=False, linecolor="#E5E7EB", ticks="outside", tickcolor="#E5E7EB"),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.2, x=0.5, xanchor="center"),
        margin=dict(t=30, r=60, b=80, l=70),
    )
)
pio.templates["atlas_dark"] = _ATLAS_TEMPLATE
pio.templates.default = "atlas_dark"

# ---------------- CSS global ----------------
def inject_css() -> None:
    st.markdown(
        """
        <style>
        #MainMenu, footer { visibility: hidden; }
        .stApp { background-color:#0A0E1A; color:#FFFFFF; }
        .block-container { max-width:1200px; padding-top:1.1rem; padding-bottom:2rem; }
        h1,h2,h3,h4 { color:#FFFFFF; }
        h1,.stMarkdown h1{ font-size:1.9rem; margin-bottom:.3rem; }
        h2,.stMarkdown h2{ font-size:1.3rem; margin-top:.8rem; margin-bottom:.2rem; }
        h3,.stMarkdown h3{ font-size:1.05rem; }
        .stMarkdown,label,.stSelectbox,.stMultiSelect,.stRadio,.stSlider{ color:#9CA3AF !important; }
        .stButton>button{ background:linear-gradient(90deg,#0D1B52,#2563EB); color:white; border-radius:8px; border:none; }
        .stButton>button:hover{ background:linear-gradient(90deg,#2563EB,#3B82F6); }
        .stSelectbox,.stMultiSelect,.stTextInput,.stDateInput,.stNumberInput,.stSlider{ background-color:#111827 !important; border-radius:8px !important; color:#FFFFFF !important; }
        .tiles{ display:flex; flex-wrap:wrap; gap:20px; justify-content:center; align-items:stretch; margin-top:10px; }
        .card{ width:320px; max-width:100%; border-radius:14px; border:1px solid #1F2937; background:#111827; box-shadow:0 4px 16px rgba(15,23,42,0.06); padding:14px 16px; display:flex; flex-direction:column; gap:8px; transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease; }
        .card:hover{ transform:translateY(-2px); box-shadow:0 14px 30px rgba(2,6,23,.20); border-color:rgba(37,99,235,.45); }
        .card h3{ margin:0; font-size:1.06rem; line-height:1.25; }
        .muted{ color:#9CA3AF; font-size:.93rem; }
        .card-footer{ display:flex; justify-content:flex-end; margin-top:6px; }
        a[data-testid="stPageLink"]{ background:#111827; border:1px solid #1F2937; padding:6px 10px; border-radius:10px; text-decoration:none; font-size:.92rem; color:#FFFFFF; }
        a[data-testid="stPageLink"]:hover{ border-color:rgba(37,99,235,.55); }
        .js-plotly-plot{ margin-bottom:26px; }

        /* KPIs */
        .kpi-box{ background:#111827; border:1px solid #1F2937; border-radius:12px; padding:14px 16px; }
        .kpi-head{ display:flex; align-items:center; justify-content:space-between; margin-bottom:6px; }
        .kpi-title{ color:#9CA3AF; font-size:.9rem; }
        .kpi-value{ color:#FFFFFF; font-size:1.6rem; font-weight:600; }
        .kpi-help{ position:relative; display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:50%; border:1px solid #374151; color:#9CA3AF; font-size:.8rem; font-weight:700; cursor:help; user-select:none; }
        .kpi-help:hover::after{ content:attr(data-tip); position:absolute; left:50%; transform:translateX(-50%); bottom:130%; background:#0B1222; color:#E5E7EB; border:1px solid #374151; border-radius:8px; padding:8px 10px; width:max-content; max-width:320px; white-space:normal; font-size:.85rem; line-height:1.2rem; box-shadow:0 8px 20px rgba(0,0,0,.25); z-index:9999; }
        .kpi-help:hover::before{ content:""; position:absolute; left:50%; transform:translateX(-50%); bottom:118%; border:6px solid transparent; border-top-color:#374151; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------------- Tarjeta home ----------------
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

# ---------------- Controles de rango + gobierno + frecuencia ----------------
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
    return None if not s else dt.date.fromisoformat(s)

def range_controls(
    dmin: dt.date | dt.datetime,
    dmax: dt.date | dt.datetime,
    key: str = "",
    show_government: bool = True,
) -> Tuple[dt.date, dt.date, str]:
    """
    Reglas:
    - La última interacción gana.
    - Al cambiar Rango rápido → se limpia Gobierno.
    - Al cambiar Gobierno → Rango rápido queda visualmente en '(ninguno)'.
    """
    rr_key     = f"rr_{key}"
    gov_key    = f"gov_{key}"
    fq_key     = f"fq_{key}"
    last_key   = f"last_{key}"      # 'rr' o 'gov'
    rr_val_key = f"rr_val_{key}"    # etiqueta visible del combo de rango

    # estado inicial
    if last_key not in st.session_state:   st.session_state[last_key]   = "rr"
    if gov_key  not in st.session_state:   st.session_state[gov_key]    = "(ninguno)"
    if rr_val_key not in st.session_state: st.session_state[rr_val_key] = "Máximo"

    # opciones (incluimos '(ninguno)' para poder mostrarlo cuando rige Gobierno)
    RANGO_CHOICES = ["(ninguno)", "1 mes", "3 meses", "6 meses", "1 año", "YTD", "2 años", "Máximo"]

    # callbacks
    def _on_rr_change():
        st.session_state[last_key] = "rr"
        st.session_state[gov_key]  = "(ninguno)"
        # guardar lo que eligió el usuario en el combo
        st.session_state[rr_val_key] = st.session_state.get(rr_key, "Máximo")

    def _on_gov_change():
        st.session_state[last_key] = "gov"
        # al elegir gobierno, mostrar '(ninguno)' en el combo de rango
        st.session_state[rr_val_key] = "(ninguno)"

    # widgets
    col1, col2, col3 = st.columns([1, 1.4, 1])

    with col1:
        # índice visible del combo de rango
        rr_index = RANGO_CHOICES.index(st.session_state[rr_val_key]) if st.session_state[rr_val_key] in RANGO_CHOICES else 0
        rango = st.selectbox(
            "Rango rápido",
            RANGO_CHOICES,
            index=rr_index,
            key=rr_key,
            on_change=_on_rr_change,
        )

    with col2:
        gov_label = "(ninguno)"
        if show_government:
            gov_index = [g[0] for g in _GOV_PERIODS].index(st.session_state[gov_key])
            gov_label = st.selectbox(
                "Gobierno",
                [g[0] for g in _GOV_PERIODS],
                index=gov_index,
                key=gov_key,
                on_change=_on_gov_change,
            )

    with col3:
        freq_label = st.selectbox("Frecuencia", ["Diaria", "Mensual (fin de mes)"], index=0, key=fq_key)

    # fechas base
    dmin = (dmin.date() if hasattr(dmin, "date") else dmin)
    dmax = (dmax.date() if hasattr(dmax, "date") else dmax)

    # helpers
    def _range_from_quick(label: str):
        # si el combo está en '(ninguno)', usamos Máximo por detrás
        label = "Máximo" if label == "(ninguno)" else label
        today = dmax
        if label == "1 mes":
            d_ini = max(dmin, today - dt.timedelta(days=31))
        elif label == "3 meses":
            d_ini = max(dmin, today - dt.timedelta(days=92))
        elif label == "6 meses":
            d_ini = max(dmin, today - dt.timedelta(days=183))
        elif label == "1 año":
            d_ini = max(dmin, today - dt.timedelta(days=365))
        elif label == "YTD":
            d_ini = dt.date(today.year, 1, 1)
        elif label == "2 años":
            d_ini = max(dmin, today - dt.timedelta(days=365 * 2))
        else:  # Máximo
            d_ini = dmin
        return d_ini, dmax

    def _range_from_gov(label: str):
        _, gini, gfin = next(g for g in _GOV_PERIODS if g[0] == label)
        gini_d = _parse_date(gini) or dmin
        gfin_d = _parse_date(gfin) or dmax
        return max(dmin, gini_d), min(dmax, gfin_d)

    # decisión: última acción gana
    if show_government and st.session_state[last_key] == "gov" and st.session_state[gov_key] != "(ninguno)":
        d_ini, d_fin = _range_from_gov(st.session_state[gov_key])
    else:
        d_ini, d_fin = _range_from_quick(st.session_state[rr_val_key])

    return d_ini, d_fin, freq_label

# ---------------- KPI con tooltip CSS ----------------
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
