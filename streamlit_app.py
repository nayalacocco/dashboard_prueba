# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import numpy as np
import textwrap

st.set_page_config(page_title="Macro Argentina – BCRA", layout="wide", page_icon="🇦🇷")
st.title("🇦🇷 Macro Argentina – BCRA (API v3, auto-actualizado)")

CSV_LONG = Path("data/monetarias_long.csv")
CAT_JSON  = Path("data/monetarias_catalogo.json")

# ---------- Carga de datos ----------
@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(CSV_LONG)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["fecha"]).sort_values(["descripcion", "fecha"])

@st.cache_data(ttl=3600)
def load_catalog():
    return pd.read_json(CAT_JSON)

# Verificaciones
if not CSV_LONG.exists() or not CAT_JSON.exists():
    st.error("No encontré los archivos esperados en /data (monetarias_long.csv y monetarias_catalogo.json). Corré el fetch.")
    st.stop()

df = load_data()
_ = load_catalog()  # por ahora no lo usamos en el front

vars_disponibles = sorted(df["descripcion"].dropna().unique().tolist())
if not vars_disponibles:
    st.error("El CSV no tiene datos válidos.")
    st.stop()

# ---------- Sidebar ----------
st.sidebar.header("Parámetros")
default_1 = next((v for v in vars_disponibles if "base monetaria" in v.lower()), vars_disponibles[0])

seleccion = st.sidebar.multiselect(
    "Seleccioná 1 o 2 variables",
    options=vars_disponibles,
    default=[default_1],
    max_selections=2,
)

if not seleccion:
    st.info("Elegí al menos una variable.")
    st.stop()

df_sel = df[df["descripcion"].isin(seleccion)].copy()
if df_sel.empty:
    st.warning("No hay datos para la selección.")
    st.stop()

# Rango de fechas global a la selección
fmin = df_sel["fecha"].min().date()
fmax = df_sel["fecha"].max().date()

c1, c2 = st.columns(2)
with c1:
    d_ini = st.date_input("Desde", value=fmin, min_value=fmin, max_value=fmax)
with c2:
    d_fin = st.date_input("Hasta", value=fmax, min_value=fmin, max_value=fmax)

if pd.to_datetime(d_ini) > pd.to_datetime(d_fin):
    d_ini, d_fin = d_fin, d_ini

mask = (df_sel["fecha"] >= pd.to_datetime(d_ini)) & (df_sel["fecha"] <= pd.to_datetime(d_fin))
df_sel = df_sel.loc[mask]
if df_sel.empty:
    st.info("No hay observaciones en el rango elegido.")
    st.stop()

# ---------- Helpers ----------
def wrap_label(label, width=40):
    return "<br>".join(textwrap.wrap(str(label), width))

legend_bottom = dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5)
margins = dict(t=50, b=120)
HEIGHT = 650

# Generador de ticks "agradables" (nice ticks) para un rango y cantidad deseada
def nice_ticks(vmin, vmax, max_ticks=6):
    if vmin == vmax:
        if vmin == 0:
            return [0]
        # expandimos un poco si rango degenerado
        vmin *= 0.9
        vmax *= 1.1
    rng = vmax - vmin
    if rng <= 0:
        rng = abs(vmin) if vmin != 0 else 1.0
    # tamaño de paso aproximado
    raw_step = rng / max(1, (max_ticks - 1))
    exp = np.floor(np.log10(raw_step))
    frac = raw_step / (10 ** exp)
    # elegimos 1, 2, 2.5, 5 o 10
    if frac <= 1:
        nice_frac = 1
    elif frac <= 2:
        nice_frac = 2
    elif frac <= 2.5:
        nice_frac = 2.5
    elif frac <= 5:
        nice_frac = 5
    else:
        nice_frac = 10
    step = nice_frac * (10 ** exp)
    tick_min = np.floor(vmin / step) * step
    tick_max = np.ceil(vmax / step) * step
    # generamos y redondeamos a evitar ruido flotante
    ticks = np.arange(tick_min, tick_max + 0.5 * step, step)
    return np.round(ticks, int(max(0, -exp)))

# Mapea ticks del eje izquierdo al rango del eje derecho preservando la posición relativa
def map_ticks(left_ticks, lmin, lmax, rmin, rmax):
    if lmax == lmin:
        return [rmin] * len(left_ticks)
    return rmin + (rmax - rmin) * (left_ticks - lmin) / (lmax - lmin)

# ---------- Gráficos ----------
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
    modo = st.radio("Modo de comparación", ["Mismo eje", "Doble eje Y", "Base 100"], index=1)

    wide = df_sel.pivot(index="fecha", columns="descripcion", values="valor").sort_index()
    s1 = wide[var1].dropna()
    s2 = wide[var2].dropna()
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

        # RANGOS de cada eje
        lmin, lmax = float(np.nanmin(s1)), float(np.nanmax(s1))
        rmin, rmax = float(np.nanmin(s2)), float(np.nanmax(s2))

        # Ticks "agradables" del eje izquierdo
        left_ticks = nice_ticks(lmin, lmax, max_ticks=7)
        # Ticks correspondientes en el eje derecho (alineados en pantalla)
        right_ticks = map_ticks(left_ticks, lmin, lmax, rmin, rmax)

        # Eje izq: muestra grilla y usa nuestros ticks
        fig.update_yaxes(
            title_text="Eje izq",
            secondary_y=False,
            showgrid=True,
            tickmode="array",
            tickvals=left_ticks,
        )
        # Eje der: NO dibuja grilla; usa tickvals mapeados para alinear con la grilla izq
        fig.update_yaxes(
            title_text="Eje der",
            secondary_y=True,
            showgrid=False,
            tickmode="array",
            tickvals=right_ticks,
            tickformat=",",   # formato con miles
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

# ---------- Descarga ----------
with st.expander("Descargar CSV (rango filtrado y selección)"):
    st.download_button(
        "Descargar",
        data=df_sel.to_csv(index=False).encode("utf-8"),
        file_name="seleccion_filtrada.csv",
        mime="text/csv",
    )
