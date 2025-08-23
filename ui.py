from __future__ import annotations
import datetime as dt
from typing import Tuple, Optional, Sequence
import hashlib
import re

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
# CSS global (branding Atlas + mosaicos + KPIs + picker)
# -------------------------------------------------------------------
def inject_css() -> None:
    st.markdown(
        """
        <style>
        /* Ocultar menú y footer */
        #MainMenu, footer { visibility: hidden; }

        /* Fondo general + tipografía */
        .stApp { background-color: #0A0E1A; color: #FFFFFF; }
        .block-container { max-width: 1200px; padding-top: 1.1rem; padding-bottom: 2rem; }

        /* Headers */
        h1, h2, h3, h4 { color: #FFFFFF; }
        h1, .stMarkdown h1 { font-size: 1.9rem; margin-bottom: .3rem; }
        h2, .stMarkdown h2 { font-size: 1.3rem; margin-top: .8rem; margin-bottom: .2rem; }
        h3, .stMarkdown h3 { font-size: 1.05rem; }

        /* Texto secundario */
        .stMarkdown, label, .stSelectbox, .stMultiSelect, .stRadio, .stSlider { color: #9CA3AF !important; }

        /* Botones */
        .stButton>button {
            background: linear-gradient(90deg, #0D1B52, #2563EB);
            color: white; border-radius: 10px; border: none;
            box-shadow: 0 0 0px rgba(37,99,235,0.0);
            transition: box-shadow .18s ease, transform .18s ease;
        }
        .stButton>button:hover { background: linear-gradient(90deg, #2563EB, #3B82F6); box-shadow:0 0 18px rgba(59,130,246,.35); transform: translateY(-1px); }

        /* Inputs */
        .stSelectbox, .stMultiSelect, .stTextInput, .stDateInput, .stNumberInput, .stSlider {
            background-color: #111827 !important; border-radius: 10px !important; color: #FFFFFF !important;
            border: 1px solid #1F2937 !important;
        }

        /* GRID de mosaicos (home) */
        .tiles { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; align-items: stretch; margin-top: 10px; }

        /* Tarjeta */
        .card {
            width: 320px; max-width: 100%;
            border-radius: 14px; border: 1px solid #1F2937; background: #111827;
            box-shadow: 0 4px 16px rgba(15,23,42,0.06);
            padding: 14px 16px; display: flex; flex-direction: column; gap: 8px;
            transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        }
        .card:hover { transform: translateY(-2px); box-shadow: 0 14px 30px rgba(2,6,23,.20); border-color: rgba(37,99,235,.45); }
        .card h3 { margin: 0; font-size: 1.06rem; line-height: 1.25; }
        .muted { color: #9CA3AF; font-size: 0.93rem; }

        /* Pie de tarjeta */
        .card-footer { display: flex; justify-content: flex-end; margin-top: 6px; }
        a[data-testid="stPageLink"] {
            background: #111827; border: 1px solid #1F2937; padding: 6px 10px; border-radius: 10px;
            text-decoration: none; font-size: 0.92rem; color: #FFFFFF;
        }
        a[data-testid="stPageLink"]:hover { border-color: rgba(37,99,235,.55); }

        /* Plotly margin fix */
        .js-plotly-plot { margin-bottom: 26px; }

        /* --------- KPI por serie (quad) --------- */
        .series-kpi .row { grid-template-columns:1fr 1fr 1fr 1fr !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------------------------------------------
# Limpieza de nombres de series  # --- NEW ---
# -------------------------------------------------------------------
_LABEL_CLEAN_MAP = [
    (re.compile(r"pr[eé]stamos?\s+personales", re.I), "Préstamos personales"),
    (re.compile(r"adelantos?.*cuenta\s+corriente", re.I), "Adelantos"),
    (re.compile(r"\bbase\s+monetaria\b", re.I), "Base monetaria"),
    (re.compile(r"\bm2\s*transaccional\b", re.I), "M2 transaccional"),
    (re.compile(r"\breservas?\b.*(internacionales)?", re.I), "Reservas internacionales"),
]

def clean_label(name: str) -> str:
    for rx, short in _LABEL_CLEAN_MAP:
        if rx.search(name):
            return short
    name = re.sub(r"\s*\(.*?\)", "", name)
    return name.strip()

def looks_percent(name: str) -> bool:
    s = name.lower()
    tokens = ["%", "en %", "tna", "tea", "variación", "variacion",
              "yoy", "mom", "interanual", "mensual"]
    return any(t in s for t in tokens)

# -------------------------------------------------------------------
# KPI “quad” (Último dato + MoM/YoY/Δ)   # --- NEW ---
# -------------------------------------------------------------------
def _fmt_pct(x):
    import math
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x:,.2f}%"

def _fmt_val(x, as_pct: bool):
    if as_pct:
        return _fmt_pct(x)
    if x is None:
        return "—"
    try:
        return f"{x:,.2f}"
    except Exception:
        return str(x)

def kpi_quad(
    title: str,
    color: str,
    last_value,
    as_percent: bool,
    mom: Optional[float],
    yoy: Optional[float],
    d_per: Optional[float],
    tip_last: str = "Último dato visible en el rango elegido.",
    tip_mom: str = "", tip_yoy: str = "", tip_per: str = "",
) -> None:
    last_fmt = _fmt_val(last_value, as_percent)
    html = f"""
    <div class="series-kpi">
      <div class="head">
        <div class="dot" style="background:{color};"></div>
        <div class="title">{title}</div>
      </div>
      <div class="row">
        <div class="cell">
          <div class="lbl">Último dato <span class="q" data-tip="{tip_last}">?</span></div>
          <div class="val">{last_fmt}</div>
        </div>
        <div class="cell">
          <div class="lbl">Mensual (MoM) <span class="q" data-tip="{tip_mom}">?</span></div>
          <div class="val">{_fmt_pct(mom)}</div>
        </div>
        <div class="cell">
          <div class="lbl">Interanual (YoY) <span class="q" data-tip="{tip_yoy}">?</span></div>
          <div class="val">{_fmt_pct(yoy)}</div>
        </div>
        <div class="cell">
          <div class="lbl">Δ en el período <span class="q" data-tip="{tip_per}">?</span></div>
          <div class="val">{_fmt_pct(d_per)}</div>
        </div>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
