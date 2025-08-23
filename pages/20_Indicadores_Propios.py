# pages/20_Indicadores_Propios.py
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import re
import streamlit as st

from ui import inject_css, range_controls
from bcra_utils import load_bcra_long, resample_series

st.set_page_config(page_title="📊 Indicadores Propios (en creación)", layout="wide")
inject_css()

# =========================
# Helpers
# =========================
def _to_series(df: pd.DataFrame, desc: str) -> pd.Series:
    s = (
        df[df["descripcion"] == desc]
        .set_index("fecha")["valor"]
        .sort_index()
        .astype(float)
    )
    return s

def _fmt_value(x: float, unit: str = "ratio") -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    if unit == "ars_per_usd":
        return f"${x:,.2f} ARS/USD"
    if unit == "percent":
        return f"{x:,.2f}%"
    return f"{x:,.2f}"

def _asof_op(s_left: pd.Series, s_right: pd.Series | float, op: str, tol_days: int = 3) -> pd.Series:
    if isinstance(s_right, (int, float)):
        if   op == "÷": return (s_left / float(s_right)).astype(float)
        elif op == "×": return (s_left * float(s_right)).astype(float)
        elif op == "+": return (s_left + float(s_right)).astype(float)
        elif op == "−": return (s_left - float(s_right)).astype(float)
        elif op == "^": return (s_left ** float(s_right)).astype(float)
        return pd.Series(dtype=float)

    s_left  = s_left.sort_index()
    s_right = s_right.sort_index()
    df_l = s_left.rename("l").to_frame().reset_index().rename(columns={"index": "fecha"})
    df_r = s_right.rename("r").to_frame().reset_index().rename(columns={"index": "fecha"})
    merged = pd.merge_asof(
        df_l, df_r, on="fecha", direction="backward",
        tolerance=pd.Timedelta(days=tol_days)
    ).dropna()
    if merged.empty:
        return pd.Series(dtype=float)
    merged = merged.set_index("fecha")
    if   op == "÷": res = merged["l"] / merged["r"]
    elif op == "×": res = merged["l"] * merged["r"]
    elif op == "+": res = merged["l"] + merged["r"]
    elif op == "−": res = merged["l"] - merged["r"]
    elif op == "^": res = merged["l"] ** merged["r"]
    else:           res = pd.Series(dtype=float)
    return res.astype(float)

def _mini_chart(title: str, y: pd.Series, y_label: str = "Valor"):
    if y.empty:
        st.info("No hay datos suficientes para graficar este indicador.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=y.index, y=y.values, mode="lines", name=title, line=dict(width=2)))
    fig.update_layout(template="atlas_dark", height=360, margin=dict(t=30, b=40, l=60, r=40), showlegend=False)
    fig.update_xaxes(title_text="Fecha")
    fig.update_yaxes(title_text=y_label)
    st.plotly_chart(fig, use_container_width=True)

# =========================
# Carga
# =========================
df = load_bcra_long()
if df.empty:
    st.error("No encontré datos del BCRA. Corré el fetch primero.")
    st.stop()
df["descripcion"] = df["descripcion"].fillna("").astype(str)
ALL = sorted(df["descripcion"].unique().tolist())

# =========================
# Alias robustos (regex)
# =========================
def find_desc(patterns: list[str]) -> str | None:
    rx = [re.compile(p, re.IGNORECASE) for p in patterns]
    for desc in ALL:
        s = desc.lower()
        if any(r.search(s) for r in rx):
            return desc
    return None

# — nombres largos reales que mostraste en las capturas (además de variantes genéricas)
DESC_BASE = find_desc([
    r"\bsaldo\s+de\s+base\s+monetaria\b",
    r"\bbase\s+monetaria\b.*\(en millones de \$\)",
    r"\bbase\s+monetaria\b",
]) or ""

DESC_RESERVAS = find_desc([
    r"\bsaldo\s+de\s+reservas\s+internacionales\b.*(excluidas\s+asignaciones\s+deg).*usd",
    r"\breservas\s+internacionales\b.*(provisorias|cifras).*d[oó]lares",
    r"\breservas\s+internacionales\b",
]) or ""

DESC_M2T = find_desc([
    r"\bsaldo\s+de\s+m2\s+transaccional\b.*sector\s+privado",
    r"\bm2\s+transaccional\b",
    r"\bm1\b",  # fallback si no hay m2t
]) or ""

DESC_M2 = find_desc([
    r"\bm2\b(?!.*transaccional)",
    r"\bm2\b",
]) or ""

DESC_PASES = find_desc([
    r"\bpases\s+pasivos\b",
    r"\bstock.*pases\s+pasivos\b",
]) or ""

s_base   = _to_series(df, DESC_BASE)   if DESC_BASE   else pd.Series(dtype=float)
s_resv   = _to_series(df, DESC_RESERVAS) if DESC_RESERVAS else pd.Series(dtype=float)
s_m2t    = _to_series(df, DESC_M2T)    if DESC_M2T    else pd.Series(dtype=float)
s_m2     = _to_series(df, DESC_M2)     if DESC_M2     else pd.Series(dtype=float)
s_pases  = _to_series(df, DESC_PASES)  if DESC_PASES  else pd.Series(dtype=float)

# =========================
# Indicadores (series completas)
# =========================
ind = {}

ind["fx_base"] = dict(
    title="FX Benchmark – Base Monetaria",
    tip=f"{DESC_BASE or 'Base monetaria'} / {DESC_RESERVAS or 'Reservas internacionales'}",
    unit="ars_per_usd",
    serie=_asof_op(s_base, s_resv, "÷", tol_days=3),
    parts=(s_base, s_resv, "ARS/USD"),
)

ind["fx_m2t"] = dict(
    title="FX Benchmark – M2 Transaccional",
    tip=f"{DESC_M2T or 'M2 transaccional (o M1)'} / {DESC_RESERVAS or 'Reservas internacionales'}",
    unit="ars_per_usd",
    serie=_asof_op(s_m2t, s_resv, "÷", tol_days=3),
    parts=(s_m2t, s_resv, "ARS/USD"),
)

ind["pasivos_base"] = dict(
    title="Pasivos remunerados / Base",
    tip=f"{DESC_PASES or 'Pases pasivos'} / {DESC_BASE or 'Base monetaria'}",
    unit="percent",
    serie=_asof_op(s_pases, s_base, "÷", tol_days=3) * 100.0,
    parts=(s_pases, s_base, "%"),
)

ind["mult_monet"] = dict(
    title="Multiplicador monetario",
    tip=f"{DESC_M2 or 'M2'} / {DESC_BASE or 'Base monetaria'}",
    unit="ratio",
    serie=_asof_op(s_m2, s_base, "÷", tol_days=3),
    parts=(s_m2, s_base, "ratio"),
)

# =========================
# UI – título + controles globales (rango/frecuencia/log)
# =========================
st.title("📊 Indicadores Propios (en creación)")
st.caption("Indicadores calculados a partir de series del BCRA. Usamos la última fecha común (con tolerancia) para numeradores y denominadores.")

# rango/frecuencia iguales a otras pestañas
# construyo un índice maestro con el máximo rango entre todas las series
all_idx = pd.Index([])
for meta in ind.values():
    if not meta["serie"].empty:
        all_idx = all_idx.union(meta["serie"].index)
if all_idx.empty:
    st.warning("No pude resolver ninguna serie base. Revisá los nombres en el alias.")
    st.stop()
dmin, dmax = all_idx.min(), all_idx.max()
d_ini, d_fin, freq_label = range_controls(dmin, dmax, key="ind_propios", show_government=True)
freq = "D" if freq_label.startswith("Diaria") else "M"

# Escala log ocular
col_log1, _ = st.columns([1,3])
with col_log1:
    log_scale = st.toggle("Escala log (indicadores)", value=False, key="log_indicadores")

# aplico rango + resample a cada serie del indicador
for meta in ind.values():
    s = meta["serie"].loc[d_ini:d_fin].dropna()
    meta["serie_vis"] = resample_series(s, freq=("D" if freq=="D" else "M"), how="last").dropna()

# =========================
# Cards con último valor + botón de gráfico
# =========================
st.subheader("Indicadores (último dato disponible con tolerancia)")
c1, c2 = st.columns(2, gap="large")
palette = ["#60A5FA", "#34D399", "#F87171", "#A78BFA"]
order = ["fx_base", "fx_m2t", "pasivos_base", "mult_monet"]
cols = [c1, c2, c1, c2]

def card(key: str, color: str, column):
    meta = ind[key]
    svis = meta["serie_vis"]
    val = _fmt_value(svis.iloc[-1] if not svis.empty else None, unit=meta["unit"])
    with column:
        st.markdown(
            f"""
            <div style="
              border:1px solid #1F2937; border-radius:14px; padding:14px 16px;
              background:linear-gradient(180deg, rgba(17,24,39,.9), rgba(23,32,50,.9));
              display:flex; align-items:center; justify-content:space-between; gap:12px;">
              <div style="display:flex; align-items:center; gap:10px;">
                <span style="width:10px;height:10px;border-radius:50%;background:{color};
                       box-shadow:0 0 10px rgba(59,130,246,.45);"></span>
                <div style="color:#E5E7EB; font-weight:600;">{meta['title']}</div>
                <span title="{meta['tip']}" style="display:inline-flex; align-items:center; justify-content:center;
                       width:16px; height:16px; border-radius:50%; border:1px solid #374151; color:#9CA3AF;
                       font-size:.72rem; cursor:help;">?</span>
              </div>
              <div style="color:#FFFFFF; font-size:1.35rem; font-weight:700;">{val}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        show = st.button("Ver gráfico (fórmula)", key=f"show_{key}")
    return show

clicked_key = None
for k, col, color in zip(order, cols, palette):
    if card(k, color, col):
        clicked_key = k

# =========================
# Gráfico del indicador seleccionado (si se clickeó) + log
# =========================
if clicked_key:
    meta = ind[clicked_key]
    s_ind = meta["serie_vis"]
    st.markdown("### Gráfico del indicador")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s_ind.index, y=s_ind.values, mode="lines", name=meta["title"], line=dict(width=2)))
    fig.update_layout(template="atlas_dark", height=420, margin=dict(t=30, b=60, l=70, r=70), showlegend=False)
    fig.update_xaxes(title_text="Fecha")
    fig.update_yaxes(title_text={
        "ars_per_usd":"ARS/USD",
        "percent":"%",
        "ratio":"Valor"
    }[meta["unit"]])
    if log_scale:
        fig.update_yaxes(type="log")
    st.plotly_chart(fig, use_container_width=True)

    # Series base de la fórmula
    s_a, s_b, ylbl = meta["parts"]
    st.caption("Series base de la fórmula")
    cA, cB = st.columns(2)
    with cA:
        _mini_chart("Numerador", resample_series(s_a.loc[d_ini:d_fin].dropna(), freq=("D" if freq=="D" else "M"), how="last"), "Nivel")
    with cB:
        _mini_chart("Denominador", resample_series(s_b.loc[d_ini:d_fin].dropna(), freq=("D" if freq=="D" else "M"), how="last"), "Nivel")

st.markdown("---")

# =========================
# Constructor de indicador propio (con ^)
# =========================
st.subheader("🔧 Crear indicador propio")

colA, colB, colC = st.columns([3, 1, 3])
with colA:
    num_var = st.selectbox("Numerador", ALL, index=0 if ALL else 0, key="ip_num")
with colB:
    op = st.selectbox("Operación", ["÷", "×", "+", "−", "^"], key="ip_op")
with colC:
    den_mode = st.radio("Tipo de denominador", ["Serie", "Constante"], horizontal=True, key="ip_den_mode")

if den_mode == "Serie":
    den_var = st.selectbox("Denominador (serie)", ALL, index=0 if ALL else 0, key="ip_den_series")
    den_value: float | pd.Series = _to_series(df, den_var) if den_var else pd.Series(dtype=float)
else:
    den_value = st.number_input("Denominador (constante)", value=1.0, step=0.1, key="ip_den_const")

if st.button("Calcular indicador", type="primary"):
    s_num = _to_series(df, num_var)
    s_calc = _asof_op(s_num, den_value if isinstance(den_value, pd.Series) else float(den_value), op, tol_days=3)
    s_calc = resample_series(s_calc.loc[d_ini:d_fin].dropna(), freq=("D" if freq=="D" else "M"), how="last")
    if s_calc.empty:
        st.warning("No se pudo calcular el indicador con los datos disponibles.")
    else:
        st.success(f"Último valor: {_fmt_value(s_calc.iloc[-1])}")
        if log_scale:
            s_plot = s_calc.replace({0: np.nan}).dropna()
            _mini_chart(f"{num_var} {op} {'(serie)' if isinstance(den_value, pd.Series) else den_value} [log]",
                        s_plot, "Valor")
        else:
            _mini_chart(f"{num_var} {op} {'(serie)' if isinstance(den_value, pd.Series) else den_value}",
                        s_calc, "Valor")
