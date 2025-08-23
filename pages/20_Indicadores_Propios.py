# pages/20_Indicadores_Propios.py
from __future__ import annotations
import unicodedata
import datetime as dt
from typing import Optional, Iterable, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import inject_css
from bcra_utils import load_bcra_long

st.set_page_config(page_title="Indicadores Propios (en creación)", layout="wide")
inject_css()

st.title("📊 Indicadores Propios (en creación)")
st.caption(
    "Indicadores calculados a partir de series del BCRA. Usamos la última fecha común "
    "(con tolerancia) para numeradores y denominadores."
)

# =========================================================
# Utilidades de normalización y búsqueda robusta de series
# =========================================================
def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # sin acentos
    return s

def _match_all_words(haystack: str, words: Iterable[str]) -> bool:
    hs = _norm(haystack)
    return all(_norm(w) in hs for w in words)

def get_series_by_alias(
    df: pd.DataFrame,
    alias_groups: Iterable[Iterable[str]],
) -> pd.Series:
    """
    Devuelve la primera serie que matchee algún grupo de alias (todas las palabras del grupo).
    alias_groups: lista de grupos, p.ej. [["reservas","internacionales","brutas"], ["reservas","brutas"]]
    """
    descs = df["descripcion"].dropna().unique().tolist()
    for aliases in alias_groups:
        for d in descs:
            if _match_all_words(d, aliases):
                s = (
                    df[df["descripcion"] == d]
                    .set_index("fecha")["valor"]
                    .sort_index()
                    .astype(float)
                )
                if not s.empty:
                    s.name = d
                    return s
    raise KeyError(f"No encontré serie para alias: {alias_groups}")

def last_aligned_pair(
    s1: pd.Series, s2: pd.Series, tolerance_days: int = 2
) -> Tuple[dt.date, Optional[float], Optional[float]]:
    """
    Toma el último punto común (permitiendo diferencia de hasta `tolerance_days`).
    Devuelve (fecha, v1, v2). Si no hay alineación, v1/v2 = None.
    """
    if s1.empty or s2.empty:
        return (None, None, None)  # type: ignore

    t = min(s1.index.max(), s2.index.max())
    v1 = s1.loc[:t].tail(1)
    v2 = s2.loc[:t].tail(1)
    if v1.empty or v2.empty:
        return (None, None, None)  # type: ignore

    d1, d2 = v1.index[-1].date(), v2.index[-1].date()
    if abs((d1 - d2).days) <= tolerance_days:
        return (max(d1, d2), float(v1.iloc[-1]), float(v2.iloc[-1]))
    # Si no, intentamos retroceder al mínimo de ambas últimas fechas
    t = min(v1.index[-1], v2.index[-1])
    v1 = s1.loc[:t].tail(1)
    v2 = s2.loc[:t].tail(1)
    if v1.empty or v2.empty:
        return (None, None, None)  # type: ignore
    d1, d2 = v1.index[-1].date(), v2.index[-1].date()
    if abs((d1 - d2).days) <= tolerance_days:
        return (max(d1, d2), float(v1.iloc[-1]), float(v2.iloc[-1]))
    return (None, None, None)  # type: ignore

def fmt_number(x: Optional[float], unit: str = "") -> str:
    if x is None:
        return "—"
    if unit == "ars_per_usd":
        return f"${x:,.2f} ARS/USD".replace(",", "X").replace(".", ",").replace("X", ".")
    if unit == "percent":
        return f"{x*100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    # default: número con miles y 2 decimales
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================
# Carga de datos
# =========================
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Corré el fetch (GitHub Actions) primero.")
    st.stop()

# =========================================================
# Alias de series (ajustables según tus nombres reales)
# =========================================================
ALIAS_BASE_TOTAL = [
    ["base", "monetaria", "total"],
    ["base", "monetaria"],
]

ALIAS_RESERVAS_BRUTAS = [
    ["reservas", "internacionales", "brutas"],
    ["reservas", "brutas"],
    ["reservas", "internacionales"],  # fallback amplio
]

ALIAS_CIRCULANTE = [
    ["billetes", "monedas", "publico"],
    ["circulacion", "monetaria"],
]

ALIAS_CUENTAS_VISTA = [
    ["cuentas", "vista", "privado"],
    ["depositos", "vista", "privado"],
]

ALIAS_M1 = [
    ["m1", "privado"],
    ["m1"],
]

ALIAS_M2 = [
    ["m2", "privado"],
    ["m2"],
]

ALIAS_M2_TRANSACCIONAL = [
    ["m2", "transaccional", "privado"],
    ["m2", "transaccional"],
]

ALIAS_PASES_PASIVOS = [
    ["pases", "pasivos", "stock"],
    ["pases", "pasivos"],
]

# =========================
# Helper de tarjeta simple
# =========================
def small_card(title: str, tooltip: str, value: str, dot_color: str = "#60A5FA"):
    st.markdown(
        f"""
        <div style="
            border:1px solid #1F2937; border-radius:14px; padding:14px 16px;
            background:linear-gradient(180deg, rgba(17,24,39,.85), rgba(10,14,26,.85));
            display:flex; align-items:center; justify-content:space-between; gap:12px;">
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="width:10px; height:10px; border-radius:50%; background:{dot_color};
                         box-shadow:0 0 10px rgba(96,165,250,.45);"></span>
            <div style="color:#E5E7EB; font-weight:600;">{title}</div>
            <span title="{tooltip}"
                  style="display:inline-flex; align-items:center; justify-content:center;
                         width:16px; height:16px; border-radius:50%; border:1px solid #374151;
                         color:#9CA3AF; font-size:.72rem; cursor:help;">?</span>
          </div>
          <div style="color:#FFFFFF; font-size:1.3rem; font-weight:700;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def mini_chart(title: str, s: pd.Series, y_label: str):
    if s.empty:
        st.info("No hay datos suficientes para graficar.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name=title, line=dict(width=2)))
    fig.update_layout(template="atlas_dark", height=280, margin=dict(t=26, b=40, l=60, r=40), showlegend=False)
    fig.update_xaxes(title_text="Fecha")
    fig.update_yaxes(title_text=y_label)
    st.plotly_chart(fig, use_container_width=True)

# =========================
# Construcción de indicadores
# =========================
try:
    s_base = get_series_by_alias(df, ALIAS_BASE_TOTAL)
except KeyError:
    st.error("No encontré **Base monetaria (Total)** en los datos.")
    st.stop()

# 1) FX Benchmark – Base Monetaria: Base / Reservas brutas
try:
    s_res = get_series_by_alias(df, ALIAS_RESERVAS_BRUTAS)
except KeyError:
    st.error("No encontré **Reservas internacionales brutas** en los datos.")
    st.stop()

date_fx1, v_base, v_res = last_aligned_pair(s_base, s_res, tolerance_days=2)
fx_base = (v_base / v_res) if (v_base and v_res and v_res != 0) else None

# 2) FX Benchmark – M2 Transaccional: (Circulante + CAV) / Reservas brutas (fallback M1)
s_circ = None
s_vista = None
try:
    s_circ = get_series_by_alias(df, ALIAS_CIRCULANTE)
except KeyError:
    pass
try:
    s_vista = get_series_by_alias(df, ALIAS_CUENTAS_VISTA)
except KeyError:
    pass

if s_circ is not None and s_vista is not None:
    # Alinear cada una con reservas por separado en la última fecha común
    date_c, v_c, v_r1 = last_aligned_pair(s_circ, s_res, tolerance_days=2)
    date_v, v_v, v_r2 = last_aligned_pair(s_vista, s_res, tolerance_days=2)
    if all(x is not None for x in (v_c, v_v, v_r1, v_r2)) and v_r1 and v_r2:
        # usamos la misma reserva (la más reciente común)
        date_fx2 = min(date_c, date_v)
        # valores al corte
        v_c_cut = float(s_circ.loc[:pd.Timestamp(date_fx2)].tail(1).iloc[-1])
        v_v_cut = float(s_vista.loc[:pd.Timestamp(date_fx2)].tail(1).iloc[-1])
        v_r_cut = float(s_res.loc[:pd.Timestamp(date_fx2)].tail(1).iloc[-1])
        fx_m2t = (v_c_cut + v_v_cut) / v_r_cut if v_r_cut else None
    else:
        fx_m2t = None
else:
    # Fallback: usar M1
    try:
        s_m1 = get_series_by_alias(df, ALIAS_M1)
        _, v_m1, v_r = last_aligned_pair(s_m1, s_res, tolerance_days=2)
        fx_m2t = (v_m1 / v_r) if (v_m1 and v_r and v_r != 0) else None
    except KeyError:
        fx_m2t = None

# 3) Pasivos remunerados / Base: Pases pasivos / Base
try:
    s_pases = get_series_by_alias(df, ALIAS_PASES_PASIVOS)
    _, v_pases, v_base_for_ratio = last_aligned_pair(s_pases, s_base, tolerance_days=2)
    ratio_pases_base = (v_pases / v_base_for_ratio) if (v_pases and v_base_for_ratio and v_base_for_ratio != 0) else None
except KeyError:
    ratio_pases_base = None

# 4) Multiplicador monetario: M2 / Base
try:
    s_m2 = get_series_by_alias(df, ALIAS_M2)
    _, v_m2, v_base_for_mult = last_aligned_pair(s_m2, s_base, tolerance_days=2)
    mult_monetario = (v_m2 / v_base_for_mult) if (v_m2 and v_base_for_mult and v_base_for_mult != 0) else None
except KeyError:
    mult_monetario = None

# =========================
# Render
# =========================
st.subheader("Indicadores (último dato disponible con tolerancia)")
c1, c2 = st.columns(2)
with c1:
    small_card(
        "FX Benchmark – Base Monetaria",
        "Fórmula: Base monetaria total / Reservas internacionales brutas",
        fmt_number(fx_base, "ars_per_usd"),
        "#60A5FA",
    )
with c2:
    small_card(
        "FX Benchmark – M2 Transaccional",
        "Fórmula: (Circulante + Cuentas a la Vista) / Reservas brutas. Si falta CAV, se usa M1.",
        fmt_number(fx_m2t, "ars_per_usd"),
        "#34D399",
    )

c3, c4 = st.columns(2)
with c3:
    small_card(
        "Pasivos remunerados / Base",
        "Fórmula: Stock de Pases Pasivos / Base monetaria total",
        fmt_number(ratio_pases_base, "percent"),
        "#F87171",
    )
with c4:
    small_card(
        "Multiplicador monetario",
        "Fórmula: M2 / Base monetaria total",
        fmt_number(mult_monetario, ""),
        "#A78BFA",
    )

# Opcional: mini-charts de las series usadas
with st.expander("Ver mini-gráficos de series base"):
    st.markdown("**Base monetaria (Total)**")
    mini_chart("Base monetaria (Total)", s_base, "Millones de $")

    st.markdown("**Reservas internacionales brutas**")
    mini_chart("Reservas brutas", s_res, "Millones de USD")

    if s_circ is not None:
        st.markdown("**Billetes y monedas en poder del público / Circulación monetaria**")
        mini_chart("Circulante", s_circ, "Millones de $")

    if s_vista is not None:
        st.markdown("**Cuentas/Depósitos a la vista (Sector Privado)**")
        mini_chart("Cuentas a la vista", s_vista, "Millones de $")

    try:
        mini_chart("Pases pasivos", s_pases, "Millones de $")
    except Exception:
        pass

    try:
        mini_chart("M2", s_m2, "Millones de $")
    except Exception:
        pass
