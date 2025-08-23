# ui.py
from __future__ import annotations
import datetime as dt
from typing import Tuple, Optional, Sequence, List, Dict
import re
import hashlib

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
# CSS global (branding + widgets + KPIs)
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

        /* Tarjetas (home) */
        .tiles { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; align-items: stretch; margin-top: 10px; }
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
        .card-footer { display: flex; justify-content: flex-end; margin-top: 6px; }
        a[data-testid="stPageLink"] {
            background: #111827; border: 1px solid #1F2937; padding: 6px 10px; border-radius: 10px;
            text-decoration: none; font-size: 0.92rem; color: #FFFFFF;
        }
        a[data-testid="stPageLink"]:hover { border-color: rgba(37,99,235,.55); }

        /* Plotly */
        .js-plotly-plot { margin-bottom: 26px; }

        /* KPI tripleta */
        .series-kpi { border:1px solid #1F2937; border-radius:14px; padding:14px 16px; background:linear-gradient(180deg, rgba(17,24,39,.9), rgba(23,32,50,.9)); margin-top:14px; backdrop-filter: blur(6px); }
        .series-kpi .head { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
        .series-kpi .dot { width:10px; height:10px; border-radius:50%; box-shadow:0 0 10px rgba(59,130,246,.45); }
        .series-kpi .title { color:#E5E7EB; font-weight:600; font-size:0.98rem; }
        .series-kpi .row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }
        .series-kpi .cell { background:#0f172a; border:1px solid #1F2937; border-radius:12px; padding:10px 12px; }
        .series-kpi .cell .lbl { color:#9CA3AF; font-size:0.85rem; display:flex; align-items:center; gap:6px; }
        .series-kpi .cell .val { color:#FFFFFF; font-size:1.35rem; font-weight:600; margin-top:4px; }
        .series-kpi .q { position:relative; display:inline-flex; align-items:center; justify-content:center; width:16px; height:16px; border-radius:50%; border:1px solid #374151; color:#9CA3AF; font-size:.72rem; cursor:help; }
        .series-kpi .q:hover::after{
          content:attr(data-tip); position:absolute; left:50%; transform:translateX(-50%); bottom:130%;
          background:#0B1222; color:#E5E7EB; border:1px solid #374151; border-radius:8px; padding:8px 10px;
          width:max-content; max-width:320px; white-space:normal; font-size:.85rem; line-height:1.2rem; box-shadow:0 8px 20px rgba(0,0,0,.25); z-index:9999;
        }
        .series-kpi .q:hover::before{ content:""; position:absolute; left:50%; transform:translateX(-50%); bottom:118%; border:6px solid transparent; border-top-color:#374151; }

        /* Leyenda split */
        .split-legend { display:flex; flex-wrap:wrap; gap:24px; justify-content:space-between; margin-top:-8px; margin-bottom:10px; }
        .split-legend .col { flex:1 1 380px; }
        .split-legend .col.right { text-align:right; }
        .split-legend .hdr { color:#9CA3AF; font-size:.9rem; margin-bottom:6px; }
        .split-legend .li { color:#E5E7EB; font-size:.95rem; margin:4px 0; display:flex; align-items:center; gap:8px; }
        .split-legend .col.right .li { justify-content:flex-end; }
        .split-legend .dot { width:10px; height:10px; border-radius:50%; display:inline-block; box-shadow:0 0 8px rgba(59,130,246,.35); }

        /* -------- Series Explorer (nuevo picker) -------- */
        .expl-wrap { border:1px solid #1F2937; border-radius:16px; background:linear-gradient(180deg, rgba(15,23,42,.75), rgba(10,14,26,.75)); padding:14px; backdrop-filter: blur(8px); box-shadow: 0 6px 30px rgba(2,6,23,.25); }
        .expl-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
        .expl-title { color:#E5E7EB; font-weight:700; }
        .expl-sub { color:#9CA3AF; font-size:.92rem; margin-top:4px; }
        .expl-badge { background:rgba(37,99,235,.15); border:1px solid rgba(37,99,235,.35); padding:4px 8px; border-radius:999px; font-size:.85rem; color:#c7d2fe; }
        .expl-clear { background:linear-gradient(90deg,#0D1B52,#2563EB); border:0; color:#fff; padding:6px 10px; border-radius:10px; cursor:pointer; }
        .expl-clear:hover { filter:brightness(1.08); box-shadow:0 0 16px rgba(59,130,246,.35); }
        .expl-search input { border-radius:12px !important; }
        .expl-left { border:1px solid #1F2937; border-radius:12px; background:#0f172a; padding:10px; }
        .expl-cat { display:flex; align-items:center; gap:10px; padding:10px; border-radius:10px; cursor:pointer; color:#E5E7EB; }
        .expl-cat:hover { background:#0b1222; }
        .expl-cat-active { background:linear-gradient(90deg, rgba(37,99,235,.15), rgba(59,130,246,.10)); border:1px solid rgba(37,99,235,.35); }
        .expl-right { border:1px solid #1F2937; border-radius:12px; background:#0f172a; padding:10px 12px; }
        .expl-empty { color:#9CA3AF; padding:12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# -------------------------------------------------------------------
# Tarjeta (home)
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
# Controles de rango + Gobierno + Frecuencia
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
) -> Tuple[dt.date, dt.date, str]:
    rr_key   = f"rr_{key}"
    gov_key  = f"gov_{key}"
    fq_key   = f"fq_{key}"
    rr_cnt   = f"rr_cnt_{key}"
    gov_cnt  = f"gov_cnt_{key}"

    if rr_key  not in st.session_state:  st.session_state[rr_key]  = "(ninguno)"
    if gov_key not in st.session_state:  st.session_state[gov_key] = "(ninguno)"
    if rr_cnt  not in st.session_state:  st.session_state[rr_cnt]  = 0
    if gov_cnt not in st.session_state:  st.session_state[gov_cnt] = 0
    if fq_key  not in st.session_state:  st.session_state[fq_key]  = "Diaria"

    rr_options  = ["(ninguno)", "1 mes", "3 meses", "6 meses", "1 año", "YTD", "2 años", "Máximo"]
    gov_options = [g[0] for g in _GOV_PERIODS]

    def _on_rr_change():
        st.session_state[rr_cnt] += 1
        if st.session_state[rr_key] != "(ninguno)":
            st.session_state[gov_key] = "(ninguno)"
    def _on_gov_change():
        st.session_state[gov_cnt] += 1
        if st.session_state[gov_key] != "(ninguno)":
            st.session_state[rr_key] = "(ninguno)"

    col1, col2, col3 = st.columns([1, 1.4, 1])

    with col1:
        rango = st.selectbox(
            "Rango rápido",
            rr_options,
            index=rr_options.index(st.session_state[rr_key]),
            key=rr_key,
            on_change=_on_rr_change,
        )

    if st.session_state[rr_key] != "(ninguno)" and st.session_state[gov_key] != "(ninguno)":
        st.session_state[gov_key] = "(ninguno)"
        st.session_state[rr_cnt] = max(st.session_state[rr_cnt], st.session_state[gov_cnt] + 1)

    with col2:
        if show_government:
            gov_label = st.selectbox(
                "Gobierno",
                gov_options,
                index=gov_options.index(st.session_state[gov_key]),
                key=gov_key,
                on_change=_on_gov_change,
            )
        else:
            gov_label = "(ninguno)"

    with col3:
        freq_label = st.selectbox(
            "Frecuencia",
            ["Diaria", "Mensual (fin de mes)"],
            index=0 if st.session_state[fq_key] == "Diaria" else 1,
            key=fq_key,
        )

    dmin = (dmin.date() if hasattr(dmin, "date") else dmin)
    dmax = (dmax.date() if hasattr(dmax, "date") else dmax)

    def _range_from_quick(sel: str):
        if sel == "(ninguno)":
            return None
        today = dmax
        if sel == "1 mes":
            d_ini = max(dmin, today - dt.timedelta(days=31))
        elif sel == "3 meses":
            d_ini = max(dmin, today - dt.timedelta(days=92))
        elif sel == "6 meses":
            d_ini = max(dmin, today - dt.timedelta(days=183))
        elif sel == "1 año":
            d_ini = max(dmin, today - dt.timedelta(days=365))
        elif sel == "YTD":
            d_ini = dt.date(today.year, 1, 1)
        elif sel == "2 años":
            d_ini = max(dmin, today - dt.timedelta(days=365 * 2))
        elif sel == "Máximo":
            d_ini = dmin
        else:
            return None
        return d_ini, dmax

    def _range_from_gov(label: str):
        if label == "(ninguno)":
            return None
        _, gini, gfin = next(g for g in _GOV_PERIODS if g[0] == label)
        gini_d = _parse_date(gini) or dmin
        gfin_d = _parse_date(gfin) or dmax
        return max(dmin, gini_d), min(dmax, gfin_d)

    if show_government and st.session_state[gov_cnt] > st.session_state[rr_cnt] and gov_label != "(ninguno)":
        d_ini, d_fin = _range_from_gov(gov_label)
    else:
        rng = _range_from_quick(rango)
        d_ini, d_fin = rng if rng else (dmin, dmax)

    return d_ini, d_fin, freq_label


# -------------------------------------------------------------------
# KPI tripleta
# -------------------------------------------------------------------
def _fmt_pct(x):
    import math
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x:,.2f}%"

def kpi_triplet(
    title: str,
    color: str,
    mom: Optional[float],
    yoy: Optional[float],
    d_per: Optional[float],
    tip_mom: str = "", tip_yoy: str = "", tip_per: str = "",
) -> None:
    html = f"""
    <div class="series-kpi">
      <div class="head">
        <div class="dot" style="background:{color};"></div>
        <div class="title">{title}</div>
      </div>
      <div class="row">
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


# -------------------------------------------------------------------
# Series Explorer Picker (buscador + categorías + checkboxes)
# -------------------------------------------------------------------
def _classify(desc: str) -> str:
    s = desc.lower()
    if re.search(r"\btasa|\bbadlar|\bplazo\s*fijo|\bcaución|\bpases?\b|\bleliq\b", s):
        return "Tasas de interés"
    if re.search(r"\bbase\s+monetaria|\bm[123]\b|\bcirculaci[óo]n|\bmonetaria", s):
        return "Agregados monetarios"
    if re.search(r"\breservas|\bbruta|\bneta|\busd|\bd[oó]lar", s):
        return "Reservas"
    return "Otros indicadores BCRA"

def _stable_key(prefix: str, text: str) -> str:
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"

def series_explorer_picker(
    options: Sequence[str],
    *,
    default: Sequence[str] | None = None,
    key: str = "series",
    max_selections: int = 3,
    title: str = "Elegí hasta 3 series para comparar.",
    subtitle: str = "Podés combinar tasas (%) con agregados o reservas. Si mezclás, el sistema usará doble eje automáticamente.",
) -> List[str]:
    state_key = f"expl_sel_{key}"
    cat_key   = f"expl_cat_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = list(default) if default else []
    if cat_key not in st.session_state:
        st.session_state[cat_key] = "Tasas de interés"

    # Build catalog
    by_cat: Dict[str, List[str]] = {"Tasas de interés": [], "Agregados monetarios": [], "Reservas": [], "Otros indicadores BCRA": []}
    for o in options:
        by_cat[_classify(o)].append(o)
    for k in by_cat:
        by_cat[k] = sorted(set(by_cat[k]))

    sel = set(st.session_state[state_key])
    active_cat = st.session_state[cat_key]

    # UI
    st.markdown('<div class="expl-wrap">', unsafe_allow_html=True)
    head_left, head_right = st.columns([1, 0.23])
    with head_left:
        st.markdown(f"<div class='expl-title'>{title}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='expl-sub'>{subtitle}</div>", unsafe_allow_html=True)
    with head_right:
        c = len(sel)
        st.markdown(f"<div class='expl-badge' style='text-align:center'>{c}/{max_selections}</div>", unsafe_allow_html=True)
        if st.button("Limpiar", key=f"expl_clear_{key}", use_container_width=True):
            sel.clear()
            st.session_state[state_key] = []

    st.markdown('<div class="expl-search">', unsafe_allow_html=True)
    q = st.text_input("Buscar variable...", value="", key=f"expl_search_{key}", label_visibility="collapsed", placeholder="Buscar variable…")
    st.markdown('</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([0.36, 0.64])

    with col_left:
        st.markdown('<div class="expl-left">', unsafe_allow_html=True)
        for cat in ["Tasas de interés", "Agregados monetarios", "Reservas", "Otros indicadores BCRA"]:
            active = " expl-cat-active" if cat == active_cat else ""
            if st.button(f"{cat}", key=_stable_key(f'expl_cat_btn_{key}', cat)):
                st.session_state[cat_key] = cat
                active_cat = cat
            st.markdown(f"<div class='expl-cat{active}'>{cat}</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="expl-right">', unsafe_allow_html=True)
        opts = by_cat.get(active_cat, [])
        if q:
            ql = q.lower()
            opts = [o for o in opts if ql in o.lower()]
        if not opts:
            st.markdown("<div class='expl-empty'>No hay resultados para el filtro actual.</div>", unsafe_allow_html=True)
        else:
            # Checkboxes
            for o in opts:
                disabled = (len(sel) >= max_selections) and (o not in sel)
                chk = st.checkbox(
                    o,
                    key=_stable_key(f"expl_chk_{key}", o),
                    value=(o in sel),
                    disabled=disabled,
                )
                if chk:
                    sel.add(o)
                else:
                    if o in sel:
                        sel.remove(o)
        st.markdown('</div>', unsafe_allow_html=True)

    st.session_state[state_key] = list(sel)
    st.markdown('</div>', unsafe_allow_html=True)
    return list(sel)


# -------------------------------------------------------------------
# KPI simple (compat con páginas que importan `kpi`)
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
