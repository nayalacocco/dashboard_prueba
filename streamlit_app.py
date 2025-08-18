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

# fuzzy finder: requiere que TODOS los keywords aparezcan (contains) en la descripción
def find_var_by_keywords(keywords, universe):
    kw = [norm(k) for k in keywords]
    for v in universe:
        nv = norm(v)
        if all(k in nv for k in kw):
            return v
    # si no hay match perfecto, probamos con que aparezca cualquiera
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

# ---------- Sidebar ----------
st.sidebar.header("Parámetros")

# 💡 Comparaciones recomendadas (cada una trae keywords para buscar)
RECS = {
    "Base monetaria vs Reservas": {
        "vars": [
            ["base monetaria", "total"],
            ["reservas", "internacionales"]
        ],
        "nota": "Compara emisión primaria (Base monetaria) con los activos externos del BCRA (Reservas)."
    },
    "Base monetaria vs Pasivos remunerados": {
        "vars": [
            ["base monetaria", "total"],
            ["pasivos", "remunerados"]  # también matchea Leliq/Pases si aparecen en la descripción
        ],
        "nota": "Mide el peso de la deuda del BCRA con el sistema financiero (Leliqs + Pases) frente a la emisión primaria."
    },
    "Reservas vs Pasivos remunerados": {
        "vars": [
            ["reservas", "internacionales"],
            ["pasivos", "remunerados"]
        ],
        "nota": "Evalúa cobertura: ¿alcanzan las reservas para respaldar los pasivos remunerados?"
    },
    "Base monetaria vs Tipo de cambio (Com. A 3500)": {
        "vars": [
            ["base monetaria", "total"],
            ["tipo de cambio", "3500"]  # suele aparecer como Com. 'A' 3500
        ],
        "nota": "Relación entre oferta de pesos y precio del dólar oficial (Comunicación A3500)."
    },
    "Base monetaria vs M2 Privado": {
        "vars": [
            ["base monetaria", "total"],
            ["m2", "privado"]
        ],
        "nota": "Transmisión: cuánto de la base se expande al dinero amplio del sector privado (M2)."
    }
}

rec_choice = st.sidebar.selectbox("💡 Comparaciones recomendadas", ["(ninguna)"] + list(RECS.keys()))

# Si hay recomendada elegida, resolvemos variables por keywords
preselected = None
nota_rec = None
if rec_choice != "(ninguna)":
    rec_def = RECS[rec_choice]
    v1 = find_var_by_keywords(rec_def["vars"][0], vars_disponibles)
    v2 = find_var_by_keywords(rec_def["vars"][1], vars_disponibles)
    preselected = [v for v in [v1, v2] if v is not None]
    nota_rec = rec_def["nota"]

# Multiselect (si hay recomendada, mostramos lo encontrado y permitimos cambiar)
default_1 = next((v for v in vars_disponibles if "base monetaria" in norm(v)), vars_disponibles[0])
seleccion = st.sidebar.multiselect(
    "Seleccioná 1 o 2 variables",
    options=vars_disponibles,
    default=(preselected if preselected else [default_1]),
    max_selections=2,
)

if not seleccion:
    st.info("Elegí al menos una variable.")
    st.stop()

# ---------- Rango de fechas ----------
df_sel_all = df[df["descripcion"].isin(seleccion)].copy()
if df_sel_all.empty:
    st.warning("No hay datos para la selección.")
    st.stop()

fmin = df_sel_all["fecha"].min().date()
fmax = df_sel_all["fecha"].max().date()

c1, c2 = st.columns(2)
with c1:
    d_ini = st.date_input("Desde", value=fmin, min_value=fmin, max_value=fmax)
with c2:
    d_fin = st.date_input("Hasta", value=fmax, min_value=fmin, max_value=fmax)

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
    serie = df_sel[df_sel["descripcion"] == var]
    fig = px.line(serie, x="fecha", y="valor", title=wrap_label(var, 60), labels={"fecha": "Fecha", "valor": "Valor"})
    fig.update_layout(legend=legend_bottom, margin=margins, height=HEIGHT)
    st.plotly_chart(fig, use_container_width=True)

    last = serie.iloc[-1]
    st.metric("Último dato visible", f"{last['valor']:,.0f}", help=f"Fecha: {last['fecha'].date()}")

else:
    var1, var2 = seleccion
    st.subheader(f"Comparación: {var1} vs {var2}")

    modo = st.radio("Modo de comparación", ["Mismo eje", "Doble eje Y", "Base 100"], index=1)

    wide = df_sel.pivot(index="fecha", columns="descripcion", values="valor").sort_index()
    s1, s2 = wide[var1].dropna(), wide[var2].dropna()
    if s1.empty or s2.empty:
        st.warning("Alguna de las variables no tiene datos en el rango seleccionado.")
        st.stop()

    if modo == "Mismo eje":
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=s1.index, y=s1, name=wrap_label(var1), mode="lines"))
        fig.add_trace(go.Scatter(x=s2.index, y=s2, name=wrap_label(var2), mode="lines"))
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
        fig.add_trace(go.Scatter(x=s1.index, y=s1, name=wrap_label(var1), mode="lines"), secondary_y=False)
        fig.add_trace(go.Scatter(x=s2.index, y=s2, name=wrap_label(var2), mode="lines"), secondary_y=True)
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

        # Eje derecho -> ticks redondos alineados a grilla izq (ajusta rango si hace falta)
        rmin, rmax = float(np.nanmin(s2)), float(np.nanmax(s2))
        right_ticks, (r0, r1) = aligned_right_ticks_round(left_ticks, rmin, rmax)
        fig.update_yaxes(
            title_text="Eje der",
            secondary_y=True,
            showgrid=False,
            tickmode="array",
            tickvals=right_ticks,
            tickformat=".2s",  # 41k, 35k, etc.
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

    # Leyenda/nota de comparación
    if rec_choice != "(ninguna)" and nota_rec:
        st.caption(f"**Nota:** {nota_rec}")
    else:
        st.caption("**Nota:** compará la dinámica de dos series del catálogo monetario del BCRA en el rango seleccionado.")

# ---------- descarga ----------
with st.expander("Descargar CSV (rango filtrado y selección)"):
    st.download_button(
        "Descargar",
        data=df_sel.to_csv(index=False).encode("utf-8"),
        file_name="seleccion_filtrada.csv",
        mime="text/csv",
    )
