# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import numpy as np
import unicodedata
import textwrap
from datetime import date, datetime

st.set_page_config(page_title="Macro Argentina – BCRA", layout="wide", page_icon="🇦🇷")
st.title("🇦🇷 Macro Argentina – BCRA (API v3, auto-actualizado)")

CSV_LONG = Path("data/monetarias_long.csv")
CAT_JSON  = Path("data/monetarias_catalogo.json")

# ---------- carga ----------
@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(CSV_LONG)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["fecha"]).sort_values(["descripcion", "fecha"])

@st.cache_data(ttl=3600)
def load_catalog():
    return pd.read_json(CAT_JSON)

if not CSV_LONG.exists() or not CAT_JSON.exists():
    st.error("No encontré los archivos esperados en /data (monetarias_long.csv y monetarias_catalogo.json). Corré el fetch.")
    st.stop()

df = load_data()
_ = load_catalog()

vars_disponibles = sorted(df["descripcion"].dropna().unique().tolist())
if not vars_disponibles:
    st.error("El CSV no tiene datos válidos.")
    st.stop()

# ---------- helpers ----------
def norm(s: str) -> str:
    """minúsculas sin acentos para matchear tolerantemente"""
    if not isinstance(s, str):
        s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.lower()

def wrap_label(label, width=40):
    return "<br>".join(textwrap.wrap(str(label), width))

# fuzzy: requiere que TODOS los keywords aparezcan (contains) en la descripción
def find_var_by_keywords(keywords, universe):
    kw = [norm(k) for k in keywords]
    for v in universe:
        nv = norm(v)
        if all(k in nv for k in kw):
            return v
    for v in universe:
        nv = norm(v)
        if any(k in nv for k in kw):
            return v
    return None

legend_bottom = dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5)
margins = dict(t=50, b=120)
HEIGHT = 650

# nice steps/ticks
def nice_step(raw_step):
    exp = np.floor(np.log10(raw_step)) if raw_step > 0 else 0
    frac = raw_step / (10 ** exp) if raw_step > 0 else 1
    if frac <= 1: nf = 1
    elif frac <= 2: nf = 2
    elif frac <= 2.5: nf = 2.5
    elif frac <= 5: nf = 5
    else: nf = 10
    return nf * (10 ** exp)

def nice_ticks(vmin, vmax, max_ticks=7):
    if vmin == vmax:
        if vmin == 0: return np.array([0.0])
        vmin *= 0.9; vmax *= 1.1
    rng = vmax - vmin
    raw = rng / max(1, (max_ticks - 1))
    step = nice_step(raw)
    t0 = np.floor(vmin / step) * step
    t1 = np.ceil(vmax / step) * step
    ticks = np.arange(t0, t1 + 0.5*step, step)
    exp = np.floor(np.log10(step)) if step > 0 else 0
    return np.round(ticks, int(max(0, -exp)))

def nice_step_for_count(vmin, vmax, count):
    if count <= 1:
        return (vmax - vmin) if vmax != vmin else 1.0
    raw = (vmax - vmin) / (count - 1)
    return nice_step(raw)

def aligned_right_ticks_round(left_ticks, rmin_data, rmax_data):
    """Eje derecho: ticks redondos alineados a la grilla del eje izquierdo, ajustando rango si hace falta"""
    N = len(left_ticks)
    if N <= 1:
        return np.array([rmin_data]), (rmin_data, rmax_data)
    step_r = nice_step_for_count(rmin_data, rmax_data, N)
    r0 = np.floor(rmin_data / step_r) * step_r
    r_end = r0 + step_r * (N - 1)
    if r_end < rmax_data:
        r_end = np.ceil(rmax_data / step_r) * step_r
        r0 = r_end - step_r * (N - 1)
    ticks_r = r0 + step_r * np.arange(N)
    return ticks_r, (r0, r_end)

def resample_series(s: pd.Series, freq: str, how: str):
    """freq: 'D','W','M'; how: 'mean' or 'last' """
    if freq == "D":
        return s
    if how == "mean":
        return s.resample(freq).mean().dropna()
    else:  # last
        return s.resample(freq).last().dropna()

# ---------- Sidebar ----------
st.sidebar.header("Parámetros")

# 💡 Comparaciones recomendadas con notas interpretativas
RECS = {
    "Base monetaria vs Reservas": {
        "vars": [
            ["base monetaria", "total"],
            ["reservas", "internacionales"]
        ],
        "nota": (
            "Compara la cantidad de pesos emitidos por el BCRA con los dólares disponibles en reservas. "
            "Si la base crece más que las reservas, hay un descalce de respaldo (más pesos sin activos externos equivalentes), "
            "lo que suele presionar al tipo de cambio y afectar la confianza en la moneda."
        )
    },
    "Base monetaria vs Pasivos remunerados": {
        "vars": [
            ["base monetaria", "total"],
            ["pasivos", "remunerados"]  # Leliqs + Pases
        ],
        "nota": (
            "Mide cuánta emisión se esteriliza con instrumentos remunerados. "
            "Si los pasivos remunerados crecen muy rápido frente a la base, el BCRA contiene liquidez hoy "
            "pero acumula una carga de intereses que presiona a futuro."
        )
    },
    "Reservas vs Pasivos remunerados": {
        "vars": [
            ["reservas", "internacionales"],
            ["pasivos", "remunerados"]
        ],
        "nota": (
            "Indica solvencia del balance: compara cobertura en dólares (reservas) frente a la deuda monetaria en pesos (Leliqs + Pases). "
            "Una brecha creciente sugiere mayor vulnerabilidad."
        )
    },
    "Base monetaria vs Tipo de cambio (Com. A 3500)": {
        "vars": [
            ["base monetaria", "total"],
            ["tipo de cambio", "3500"]
        ],
        "nota": (
            "Relación entre oferta de pesos y cotización oficial del dólar. "
            "Si la base crece por encima del tipo de cambio, puede haber atraso cambiario; "
            "si el tipo de cambio se acelera, refleja devaluaciones o correcciones."
        )
    },
    "Base monetaria vs M2 Privado": {
        "vars": [
            ["base monetaria", "total"],
            ["m2", "privado"]
        ],
        "nota": (
            "Evalúa transmisión monetaria: si M2 crece más que la base, el sistema financiero multiplica la liquidez; "
            "si crece menos, hay más esterilización o menor llegada al público."
        )
    }
}

rec_choice = st.sidebar.selectbox("💡 Comparaciones recomendadas", ["(ninguna)"] + list(RECS.keys()))

# Resolver vars de recomendada (si aplica)
preselected = None
nota_rec = None
if rec_choice != "(ninguna)":
    rec_def = RECS[rec_choice]
    v1 = find_var_by_keywords(rec_def["vars"][0], vars_disponibles)
    v2 = find_var_by_keywords(rec_def["vars"][1], vars_disponibles)
    preselected = [v for v in [v1, v2] if v is not None]
    nota_rec = rec_def["nota"]

# Multiselect (permitimos cambiar manualmente)
default_1 = next((v for v in vars_disponibles if "base monetaria" in norm(v)), vars_disponibles[0])
seleccion = st.sidebar.multiselect(
    "Seleccioná 1 o 2 variables",
    options=vars_disponibles,
    default=(preselected if preselected else [default_1]),
    max_selections=2,
)

# Frecuencia
freq_label = st.sidebar.selectbox("Frecuencia", ["Diaria", "Semanal (promedio)", "Mensual (fin de mes)"])
if freq_label.startswith("Diaria"):
    FREQ_CODE, HOW = "D", "last"
elif "Semanal" in freq_label:
    FREQ_CODE, HOW = "W", "mean"
else:
    FREQ_CODE, HOW = "M", "last"

if not seleccion:
    st.info("Elegí al menos una variable.")
    st.stop()

# ---------- Rango rápido ----------
df_sel_all = df[df["descripcion"].isin(seleccion)].copy()
if df_sel_all.empty:
    st.warning("No hay datos para la selección.")
    st.stop()

# límites brutos
fmin_total = df_sel_all["fecha"].min().date()
fmax_total = df_sel_all["fecha"].max().date()

# presets
preset = st.radio(
    "Rango rápido",
    ["Último mes", "Últimos 3 meses", "Últimos 6 meses", "Último año", "YTD", "Últimos 2 años", "Máximo", "Personalizado"],
    horizontal=True,
    index=3  # por defecto: último año
)

today = fmax_total  # última fecha disponible en datos
def add_months(d, m):
    # mover meses de forma simple
    y = d.year + (d.month - 1 + m) // 12
    m2 = (d.month - 1 + m) % 12 + 1
    day = min(d.day, [31,
        29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
        31,30,31,30,31,31,30,31,30,31][m2-1])
    return date(y, m2, day)

if preset == "Último mes":
    d_ini_preset, d_fin_preset = add_months(today, -1), today
elif preset == "Últimos 3 meses":
    d_ini_preset, d_fin_preset = add_months(today, -3), today
elif preset == "Últimos 6 meses":
    d_ini_preset, d_fin_preset = add_months(today, -6), today
elif preset == "Último año":
    d_ini_preset, d_fin_preset = add_months(today, -12), today
elif preset == "YTD":
    d_ini_preset, d_fin_preset = date(today.year, 1, 1), today
elif preset == "Últimos 2 años":
    d_ini_preset, d_fin_preset = add_months(today, -24), today
elif preset == "Máximo":
    d_ini_preset, d_fin_preset = fmin_total, fmax_total
else:
    d_ini_preset, d_fin_preset = fmin_total, fmax_total

# Inputs de fechas (si Personalizado, el usuario ajusta; si no, mostramos el rango actual)
c1, c2 = st.columns(2)
with c1:
    d_ini = st.date_input("Desde", value=d_ini_preset, min_value=fmin_total, max_value=fmax_total)
with c2:
    d_fin = st.date_input("Hasta", value=d_fin_preset, min_value=fmin_total, max_value=fmax_total)

# Si no es personalizado, forzamos el rango a la selección del preset
if preset != "Personalizado":
    d_ini, d_fin = d_ini_preset, d_fin_preset

if pd.to_datetime(d_ini) > pd.to_datetime(d_fin):
    d_ini, d_fin = d_fin, d_ini

mask = (df_sel_all["fecha"] >= pd.to_datetime(d_ini)) & (df_sel_all["fecha"] <= pd.to_datetime(d_fin))
df_sel = df_sel_all.loc[mask]
if df_sel.empty:
    st.info("No hay observaciones en el rango elegido.")
    st.stop()

# ---------- gráfico ----------
if len(seleccion) == 1:
    var = seleccion[0]
    serie = df_sel[df_sel["descripcion"] == var].set_index("fecha")["valor"].sort_index()
    serie = resample_series(serie, FREQ_CODE, HOW).reset_index().rename(columns={"index":"fecha"})
    fig = px.line(serie, x="fecha", y="valor", title=wrap_label(var, 60), labels={"fecha": "Fecha", "valor": "Valor"})
    fig.update_layout(legend=legend_bottom, margin=margins, height=HEIGHT)
    st.plotly_chart(fig, use_container_width=True)

    last = serie.iloc[-1]
    st.metric("Último dato visible", f"{last['valor']:,.0f}", help=f"Fecha: {pd.to_datetime(last['fecha']).date()}")

else:
    var1, var2 = seleccion
    st.subheader(f"Comparación: {var1} vs {var2}")

    modo = st.radio("Modo de comparación", ["Mismo eje", "Doble eje Y", "Base 100"], index=1)

    wide_raw = df_sel.pivot(index="fecha", columns="descripcion", values="valor").sort_index()
    # resampleamos ambas al mismo índice temporal
    idx = pd.date_range(start=pd.to_datetime(d_ini), end=pd.to_datetime(d_fin), freq=FREQ_CODE)
    s1 = resample_series(wide_raw[var1].dropna().asfreq("D").interpolate(), FREQ_CODE, HOW).reindex(idx, method=None).dropna()
    s2 = resample_series(wide_raw[var2].dropna().asfreq("D").interpolate(), FREQ_CODE, HOW).reindex(idx, method=None).dropna()

    # alineamos por índice tras resample
    common_idx = s1.index.intersection(s2.index)
    s1, s2 = s1.loc[common_idx], s2.loc[common_idx]
    if s1.empty or s2.empty:
        st.warning("No hay datos suficientes tras aplicar el rango/frecuencia.")
        st.stop()

    if modo == "Mismo eje":
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s1.index, y=s1.values, name=wrap_label(var1), mode="lines"))
        fig.add_trace(go.Scatter(x=s2.index, y=s2.values, name=wrap_label(var2), mode="lines"))
        fig.update_layout(
            title=wrap_label(f"{var1} y {var2} (mismo eje)", 60),
            xaxis_title="Fecha",
            yaxis_title="Valor",
            legend=legend_bottom,
            margin=margins,
            height=HEIGHT,
        )

    elif modo == "Doble eje Y":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=s1.index, y=s1.values, name=wrap_label(var1), mode="lines"), secondary_y=False)
        fig.add_trace(go.Scatter(x=s2.index, y=s2.values, name=wrap_label(var2), mode="lines"), secondary_y=True)
        fig.update_xaxes(title_text="Fecha")

        # Eje izquierdo -> grilla con ticks agradables
        lmin, lmax = float(np.nanmin(s1)), float(np.nanmax(s1))
        left_ticks = nice_ticks(lmin, lmax, max_ticks=7)
        fig.update_yaxes(
            title_text="Eje izq",
            secondary_y=False,
            showgrid=True,
            tickmode="array",
            tickvals=left_ticks,
        )

        # Eje derecho -> ticks redondos alineados a la grilla izq (ajusta rango)
        rmin, rmax = float(np.nanmin(s2)), float(np.nanmax(s2))
        right_ticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)
        fig.update_yaxes(
            title_text="Eje der",
            secondary_y=True,
            showgrid=False,
            tickmode="array",
            tickvals=right_ticks,
            tickformat=".2s",  # 40k, 50k, etc.
            range=[r0, r1],
        )

        fig.update_layout(
            title=wrap_label(f"{var1} vs {var2} (doble eje Y)", 60),
            legend=legend_bottom,
            margin=margins,
            height=HEIGHT,
        )

    else:  # Base 100
        b1, b2 = s1.iloc[0], s2.iloc[0]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s1.index, y=(s1/b1)*100, name=wrap_label(var1), mode="lines"))
        fig.add_trace(go.Scatter(x=s2.index, y=(s2/b2)*100, name=wrap_label(var2), mode="lines"))
        fig.update_layout(
            title=wrap_label(f"{var1} vs {var2} (Base 100)", 60),
            xaxis_title="Fecha",
            yaxis_title="Índice (Base 100)",
            legend=legend_bottom,
            margin=margins,
            height=HEIGHT,
        )

    st.plotly_chart(fig, use_container_width=True)

    # Nota interpretativa
    if rec_choice != "(ninguna)" and nota_rec:
        st.caption(f"**Nota:** {nota_rec}")
    else:
        st.caption("**Nota:** compará la dinámica de dos series del catálogo monetario del BCRA en el rango seleccionado.")

# ---------- descarga ----------
with st.expander("Descargar CSV (rango filtrado y selección)"):
    # armamos dataset filtrado y resampleado según lo que se ve
    if len(seleccion) == 1:
        var = seleccion[0]
        out = df[(df["descripcion"] == var) & (df["fecha"].between(pd.to_datetime(d_ini), pd.to_datetime(d_fin)))].copy()
    else:
        out = df[(df["descripcion"].isin(seleccion)) & (df["fecha"].between(pd.to_datetime(d_ini), pd.to_datetime(d_fin)))].copy()
    st.download_button(
        "Descargar",
        data=out.to_csv(index=False).encode("utf-8"),
        file_name="seleccion_filtrada.csv",
        mime="text/csv",
    )
