# pages/20_Indicadores_Propios.py
import datetime as dt
from typing import Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import inject_css  # reuso tu CSS base
from bcra_utils import load_bcra_long, find_first

st.set_page_config(page_title="Indicadores Propios (en creación)", layout="wide")
inject_css()

st.title("📊 Indicadores Propios (en creación)")

st.caption(
    "Indicadores calculados a partir de series del BCRA. "
    "Usamos la última fecha común (con tolerancia) para numeradores y denominadores."
)

# =============== utilidades =================
def _fmt_value(x, unit: str) -> str:
    if x is None or pd.isna(x):
        return "—"
    if unit == "ars_per_usd":
        # AR$/USD con separador de miles y 2 decimales
        return f"${x:,.2f} ARS/USD}".replace(",", "X").replace(".", ",").replace("X", ".")
    if unit == "pct":
        return f"{x*100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    # ratio simple
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _nearest_common_date(a: pd.Series, b: pd.Series, max_days: int = 4) -> Optional[pd.Timestamp]:
    """Devuelve la última fecha t tal que existen a<=t y b<=t (con tolerancia de max_days hacia atrás)."""
    if a.empty or b.empty:
        return None
    ta = a.index.max()
    tb = b.index.max()
    t = min(ta, tb)
    # buscar valores no nulos hacia atrás hasta max_days
    for d in range(max_days + 1):
        tt = t - pd.Timedelta(days=d)
        if tt < a.index.min() or tt < b.index.min():
            break
        va = a.loc[:tt].dropna()
        vb = b.loc[:tt].dropna()
        if not va.empty and not vb.empty:
            return tt
    return None

def _get_series(df: pd.DataFrame, name_like: str) -> pd.Series:
    """Busca por nombre 'parecido' usando find_first y devuelve la serie indexada por fecha (float)."""
    all_desc = df["descripcion"].dropna().astype(str).unique().tolist()
    target = find_first(all_desc, *name_like.split("|"))
    if not target:
        raise KeyError(f"No encontré serie para: {name_like}")
    s = (
        df[df["descripcion"] == target]
        .set_index("fecha")["valor"]
        .astype(float)
        .sort_index()
    )
    return s

def _mini_chart(title: str, series: pd.Series):
    series = series.dropna()
    if series.empty:
        st.info("No hay datos suficientes para este gráfico.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines", name=title, line=dict(width=2)))
    fig.update_layout(template="atlas_dark", height=260, margin=dict(t=30, b=40, l=60, r=40), showlegend=False)
    fig.update_xaxes(title_text="Fecha")
    fig.update_yaxes(title_text=title)
    st.plotly_chart(fig, use_container_width=True)

# =============== datos ===============
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Corré el fetch primero.")
    st.stop()

# normalizo
df["descripcion"] = df["descripcion"].fillna("").astype(str)

# Intentos de nombre (ajustá si tus descripciones difieren)
# Reservas brutas:
s_res = _get_series(df, "reservas|brutas")
# Base monetaria (total):
s_base = _get_series(df, "base|monetaria|total")
# M2 (o M2 transaccional)
try:
    s_m2t = _get_series(df, "m2 transaccional|m2")
except Exception:
    s_m2t = _get_series(df, "m2")
# Circulante + Cuentas a la vista (si las tenés separadas)
# si no, usamos M1 como fallback
try:
    s_circulante = _get_series(df, "circulación monetaria|circulante")
    s_cav = _get_series(df, "cuentas a la vista|vista")
    s_circav = (s_circulante + s_cav).dropna()
except Exception:
    try:
        s_circav = _get_series(df, "m1")
    except Exception:
        s_circav = None

# Pasivos remunerados (pases pasivos)
s_pases = _get_series(df, "pases|pasivos")

# =============== indicadores ===============
def _ratio_at_common(a: pd.Series, b: pd.Series, unit: str, max_days=4) -> Tuple[Optional[float], Optional[pd.Timestamp]]:
    t = _nearest_common_date(a, b, max_days=max_days)
    if t is None:
        return None, None
    va = a.loc[:t].dropna().iloc[-1]
    vb = b.loc[:t].dropna().iloc[-1]
    if vb == 0:
        return None, t
    val = va / vb
    return val, t

cards = []

# 1) FX Benchmark - Base Monetaria = Base / Reservas (ARS / USD)
fx_base_val, fx_base_t = _ratio_at_common(s_base, s_res, unit="ars_per_usd")
cards.append({
    "title": "FX Benchmark – Base Monetaria",
    "tooltip": "Base monetaria / Reservas internacionales brutas (última fecha común)",
    "value": _fmt_value(fx_base_val, "ars_per_usd"),
    "date": fx_base_t,
    "series": (s_base / s_res).dropna(),
})

# 2) FX Benchmark - M2 Transaccional = (Circulante + CAV) / Reservas  (fallback: M1)
if s_circav is not None:
    fx_m2t_val, fx_m2t_t = _ratio_at_common(s_circav, s_res, unit="ars_per_usd")
    fx_m2t_series = (s_circav / s_res).dropna()
else:
    fx_m2t_val, fx_m2t_t = _ratio_at_common(s_m2t, s_res, unit="ars_per_usd")
    fx_m2t_series = (s_m2t / s_res).dropna()

cards.append({
    "title": "FX Benchmark – M2 Transaccional",
    "tooltip": "(Circulante + Cuentas a la vista) / Reservas (fallback: M1 si no hay CAV)",
    "value": _fmt_value(fx_m2t_val, "ars_per_usd"),
    "date": fx_m2t_t,
    "series": fx_m2t_series,
})

# 3) Pasivos remunerados / Base Monetaria = Pases Pasivos / Base
pr_base_val, pr_base_t = _ratio_at_common(s_pases, s_base, unit="ratio")
cards.append({
    "title": "Pasivos Remunerados / Base Monetaria",
    "tooltip": "Pases pasivos / Base monetaria (última fecha común)",
    "value": _fmt_value(pr_base_val, "ratio"),
    "date": pr_base_t,
    "series": (s_pases / s_base).dropna(),
})

# 4) Multiplicador Monetario = M2 / Base
mult_val, mult_t = _ratio_at_common(s_m2t, s_base, unit="ratio")
cards.append({
    "title": "Multiplicador Monetario",
    "tooltip": "M2 / Base monetaria (última fecha común)",
    "value": _fmt_value(mult_val, "ratio"),
    "date": mult_t,
    "series": (s_m2t / s_base).dropna(),
})

# =============== render sin HTML raro (nativo Streamlit) ===============
st.divider()
st.subheader("Indicadores (último dato comparable)")

for card in cards:
    with st.container(border=True):
        top = st.columns([0.8, 0.2])
        with top[0]:
            # título + help nativo
            st.markdown(f"**{card['title']}**")
            st.caption(card["tooltip"])
        with top[1]:
            # valor como metric (nativo) con help
            st.metric(label="Valor", value=card["value"], help=card["tooltip"])

        # fecha de cálculo
        if card["date"] is not None:
            st.caption(f"Fecha de referencia: {pd.to_datetime(card['date']).date().isoformat()}")

        # gráfico opcional
        with st.expander("Ver evolución", expanded=False):
            _mini_chart(card["title"], card["series"])
