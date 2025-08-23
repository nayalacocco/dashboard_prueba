# pages/20_Indicadores_Propios.py
from __future__ import annotations
import datetime as dt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import inject_css
from bcra_utils import load_bcra_long

st.set_page_config(page_title="📊 Indicadores Propios (en creación)", layout="wide")
inject_css()

# =========================
# Helpers comunes
# =========================
def _to_series(df: pd.DataFrame, desc: str) -> pd.Series:
    """Devuelve una serie (fecha->valor) asegurando float y fecha como DatetimeIndex."""
    s = (
        df[df["descripcion"] == desc]
        .set_index("fecha")["valor"]
        .sort_index()
        .astype(float)
    )
    # normalizo a fecha (sin hora) para evitar desalineaciones por tz
    if isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index).date
        s.index = pd.to_datetime(s.index)
    return s

def _fmt_value(x: float, unit: str = "ratio") -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if unit == "ars_per_usd":
        return f"${x:,.2f} ARS/USD"
    if unit == "percent":
        return f"{x:,.2f}%"
    return f"{x:,.2f}"

def _mini_chart(title: str, y: pd.Series, y_label: str = "Valor"):
    if y.empty:
        st.info("No hay datos suficientes para graficar este indicador.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=y.index, y=y.values, mode="lines", name=title, line=dict(width=2)))
    fig.update_layout(
        template="atlas_dark", height=320,
        margin=dict(t=30, b=40, l=60, r=40), showlegend=False,
    )
    fig.update_xaxes(title_text="Fecha")
    fig.update_yaxes(title_text=y_label)
    st.plotly_chart(fig, use_container_width=True)

def _asof_div(s_num: pd.Series, s_den: pd.Series, tol_days: int = 3) -> pd.Series:
    """Une por fecha usando el valor más reciente anterior (tipo merge_asof) con tolerancia en días."""
    if s_num.empty or s_den.empty:
        return pd.Series(dtype=float)

    # aseguró índice datetime y sin duplicados
    s_num = s_num[~s_num.index.duplicated(keep="last")]
    s_den = s_den[~s_den.index.duplicated(keep="last")]
    s_num = s_num.sort_index()
    s_den = s_den.sort_index()

    # usamos merge_asof (tolerancia en días calendario; suficiente para 2d hábiles aprox.)
    df_num = s_num.rename("num").to_frame().reset_index().rename(columns={"index": "fecha"})
    df_den = s_den.rename("den").to_frame().reset_index().rename(columns={"index": "fecha"})
    merged = pd.merge_asof(df_num, df_den, on="fecha", direction="backward", tolerance=pd.Timedelta(days=tol_days))
    merged = merged.dropna()
    merged = merged.set_index("fecha")
    return (merged["num"] / merged["den"]).astype(float)

def _asof_op(s_left: pd.Series, s_right: pd.Series | float, op: str, tol_days: int = 3) -> pd.Series:
    """Operación genérica entre serie y (serie o constante) con join asof y tolerancia."""
    if isinstance(s_right, (int, float)):
        if op == "÷":
            return (s_left / float(s_right)).astype(float)
        if op == "×":
            return (s_left * float(s_right)).astype(float)
        if op == "+":
            return (s_left + float(s_right)).astype(float)
        if op == "−":
            return (s_left - float(s_right)).astype(float)
        if op == "^":
            return (s_left ** float(s_right)).astype(float)
        return pd.Series(dtype=float)

    # si right es serie, alinear por asof
    s_left = s_left.sort_index()
    s_right = s_right.sort_index()
    df_l = s_left.rename("l").to_frame().reset_index().rename(columns={"index": "fecha"})
    df_r = s_right.rename("r").to_frame().reset_index().rename(columns={"index": "fecha"})
    merged = pd.merge_asof(df_l, df_r, on="fecha", direction="backward", tolerance=pd.Timedelta(days=tol_days)).dropna()
    merged = merged.set_index("fecha")

    if merged.empty:
        return pd.Series(dtype=float)

    if op == "÷":
        res = merged["l"] / merged["r"]
    elif op == "×":
        res = merged["l"] * merged["r"]
    elif op == "+":
        res = merged["l"] + merged["r"]
    elif op == "−":
        res = merged["l"] - merged["r"]
    elif op == "^":
        res = merged["l"] ** merged["r"]
    else:
        res = pd.Series(dtype=float)
    return res.astype(float)

# =========================
# Carga y alias de series
# =========================
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Corré el fetch primero.")
    st.stop()

df["descripcion"] = df["descripcion"].fillna("").astype(str)
ALL_VARS = sorted(df["descripcion"].unique().tolist())
LOWER_SET = {s.lower(): s for s in ALL_VARS}

def _find_by_tokens(token_groups: list[list[str]]) -> str | None:
    """Devuelve la primera descripción que contenga TODOS los tokens (case-insensitive) en algún grupo."""
    for group in token_groups:
        g = [t.lower() for t in group]
        for desc in ALL_VARS:
            ld = desc.lower()
            if all(t in ld for t in g):
                return desc
    return None

# Alias flexibles (ajustados para tu naming)
ALIAS = dict(
    base=[["base", "monetaria", "total"], ["base", "monetaria"]],
    reservas_brutas=[["reservas", "internacionales", "brutas"], ["reservas", "brutas"]],
    circulante=[["circulación", "monetaria"], ["circulante"]],
    cuentas_vista=[["cuentas", "vista"], ["cuentas", "a", "la", "vista"]],
    m1=[["m1", "privado"], ["m1"]],
    m2=[["m2", "privado"], ["m2"]],
    m2_transaccional=[["m2", "transaccional"], ["saldo", "m2", "transaccional"]],
    pases_pasivos=[["pases", "pasivos"], ["stock", "pases", "pasivos"]],
)

def get_alias(name: str) -> str | None:
    """Busca por alias (clave del dict ALIAS)."""
    if name not in ALIAS:
        return None
    return _find_by_tokens(ALIAS[name])

# =========================
# Título y bajada
# =========================
st.title("📊 Indicadores Propios (en creación)")
st.caption("Indicadores calculados a partir de series del BCRA. Usamos la última fecha común (con tolerancia) para numeradores y denominadores.")

# =========================
# Resolver series base necesarias
# =========================
try:
    s_base = _to_series(df, get_alias("base") or "")
    s_resv = _to_series(df, get_alias("reservas_brutas") or "")
except Exception:
    s_base, s_resv = pd.Series(dtype=float), pd.Series(dtype=float)

# M2 transaccional: preferimos la serie específica; si no hay, usamos M1 como fallback (según tu pedido anterior).
desc_m2t = get_alias("m2_transaccional") or get_alias("m1")
s_m2t = _to_series(df, desc_m2t) if desc_m2t else pd.Series(dtype=float)

# M2 total
desc_m2 = get_alias("m2")
s_m2 = _to_series(df, desc_m2) if desc_m2 else pd.Series(dtype=float)

# Pasivos remunerados (pases pasivos)
desc_pases = get_alias("pases_pasivos")
s_pases = _to_series(df, desc_pases) if desc_pases else pd.Series(dtype=float)

# =========================
# Cálculo de indicadores (serie completa + último)
# =========================
ind_series: dict[str, dict] = {}

# 1) FX Benchmark - Base / Reservas
fx_base = _asof_op(s_base, s_resv, "÷", tol_days=3)
ind_series["fx_base"] = dict(
    title="FX Benchmark – Base Monetaria",
    tip="Base Monetaria / Reservas internacionales brutas",
    unit="ars_per_usd",
    serie=fx_base,
)

# 2) FX Benchmark - M2 Transaccional / Reservas (o M1 si no hay M2T)
fx_m2t = _asof_op(s_m2t, s_resv, "÷", tol_days=3)
ind_series["fx_m2t"] = dict(
    title="FX Benchmark – M2 Transaccional",
    tip="(M2 transaccional del SP) / Reservas internacionales brutas. Si no hay M2T, se usa M1.",
    unit="ars_per_usd",
    serie=fx_m2t,
)

# 3) Pasivos remunerados / Base
pasivos_base = _asof_op(s_pases, s_base, "÷", tol_days=3) * 100.0  # porcentaje
ind_series["pasivos_base"] = dict(
    title="Pasivos remunerados / Base",
    tip="Pases pasivos / Base monetaria",
    unit="percent",
    serie=pasivos_base,
)

# 4) Multiplicador monetario = M2 / Base
mult_monet = _asof_op(s_m2, s_base, "÷", tol_days=3)
ind_series["mult_monet"] = dict(
    title="Multiplicador monetario",
    tip="M2 / Base monetaria",
    unit="ratio",
    serie=mult_monet,
)

# =========================
# Render cards + charts
# =========================
st.subheader("Indicadores (último dato disponible con tolerancia)")
c1, c2 = st.columns(2, gap="large")

def card(title: str, tip: str, value: str, color: str = "#60A5FA"):
    st.markdown(
        f"""
        <div style="
            border:1px solid #1F2937; border-radius:14px; padding:14px 16px;
            background:linear-gradient(180deg, rgba(17,24,39,.9), rgba(23,32,50,.9)); 
            display:flex; align-items:center; justify-content:space-between; gap:12px;
        ">
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="width:10px; height:10px; border-radius:50%; background:{color};
                         box-shadow:0 0 10px rgba(59,130,246,.45);"></span>
            <div style="color:#E5E7EB; font-weight:600;">{title}</div>
            <span title="{tip}" style="display:inline-flex; align-items:center; justify-content:center;
                         width:16px; height:16px; border-radius:50%; border:1px solid #374151; 
                         color:#9CA3AF; font-size:.72rem; cursor:help;">?</span>
          </div>
          <div style="color:#FFFFFF; font-size:1.35rem; font-weight:700;">{value}</div>
        </div>
        """, unsafe_allow_html=True
    )

palette = ["#60A5FA", "#34D399", "#F87171", "#A78BFA"]

# 2 columnas: izq dos primeros, der dos siguientes
keys_order = ["fx_base", "fx_m2t", "pasivos_base", "mult_monet"]
cols = [c1, c2, c1, c2]
for (k, col, color) in zip(keys_order, cols, palette):
    meta = ind_series[k]
    serie = meta["serie"]
    val = _fmt_value(serie.iloc[-1] if not serie.empty else None, unit=meta["unit"])
    with col:
        card(meta["title"], meta["tip"], val, color=color)

# Expander con gráficos (serie del indicador + series base si aporta)
with st.expander("Ver mini-gráficos de indicadores y series base", expanded=False):
    g1, g2 = st.columns(2, gap="large")
    with g1:
        _mini_chart("FX Benchmark – Base/Reservas", ind_series["fx_base"]["serie"], "ARS/USD")
        _mini_chart("Pasivos remunerados / Base (%)", ind_series["pasivos_base"]["serie"], "%")
    with g2:
        _mini_chart("FX Benchmark – M2T/Reservas", ind_series["fx_m2t"]["serie"], "ARS/USD")
        _mini_chart("Multiplicador monetario (M2/Base)", ind_series["mult_monet"]["serie"], "ratio")

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.caption("Series base (para referencia)")
    b1, b2 = st.columns(2, gap="large")
    with b1:
        _mini_chart("Base monetaria (nivel)", s_base, "millones de $")
        _mini_chart("Reservas internacionales brutas (nivel)", s_resv, "millones de USD (según BCRA)")
    with b2:
        _mini_chart("M2 Transaccional / M1 (nivel)", s_m2t, "millones de $")
        _mini_chart("M2 (nivel)", s_m2, "millones de $")

# =========================
# Constructor interactivo de indicadores
# =========================
st.markdown("---")
st.subheader("🔧 Crear indicador propio")

colA, colB, colC = st.columns([3, 1, 3])
with colA:
    num_var = st.selectbox("Numerador", ALL_VARS, index=ALL_VARS.index(ALL_VARS[0]) if ALL_VARS else 0, key="ip_num")
with colB:
    op = st.selectbox("Operación", ["÷", "×", "+", "−", "^"], key="ip_op")
with colC:
    den_mode = st.radio("Tipo de denominador", ["Serie", "Constante"], horizontal=True, key="ip_den_mode")

if den_mode == "Serie":
    den_var = st.selectbox("Denominador (serie)", ALL_VARS, index=0 if ALL_VARS else 0, key="ip_den_series")
    den_value: float | pd.Series = _to_series(df, den_var) if den_var else pd.Series(dtype=float)
else:
    den_value = st.number_input("Denominador (constante)", value=1.0, step=0.1, key="ip_den_const")

if st.button("Calcular indicador", type="primary"):
    s_num = _to_series(df, num_var)
    if isinstance(den_value, pd.Series):
        s_calc = _asof_op(s_num, den_value, op, tol_days=3)
    else:
        s_calc = _asof_op(s_num, float(den_value), op, tol_days=3)

    if s_calc.empty:
        st.warning("No se pudo calcular el indicador con los datos disponibles.")
    else:
        last = s_calc.iloc[-1]
        st.success(f"Último valor: {_fmt_value(last, 'ratio')}")
        _mini_chart(f"{num_var} {op} {'(serie)' if isinstance(den_value, pd.Series) else den_value}", s_calc, "Valor")
