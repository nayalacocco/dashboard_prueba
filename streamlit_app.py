# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Visualizador Económico v3", layout="wide")
st.title("Visualizador de Excel Monetario v3 📊")

file = st.file_uploader("Subí tu Excel (.xlsx)", type=["xlsx"])
if not file:
    st.info("Esperando archivo…")
    st.stop()

# 1) elegir hoja
xls = pd.ExcelFile(file)
sheet = st.selectbox("Hoja a usar", xls.sheet_names, index=(xls.sheet_names.index("DATOS | DATA") if "DATOS | DATA" in xls.sheet_names else 0))
df = xls.parse(sheet, header=None)

st.caption("Elegí la fila que contiene los encabezados (probá hasta ver etiquetas reales).")
hdr_row = st.number_input("Fila de encabezados (0-index)", min_value=0, max_value=max(200, len(df)-1), value=6, step=1)

# 2) reconstruir dataframe con ese header
df = xls.parse(sheet, header=int(hdr_row))
df = df.dropna(axis=1, how="all").dropna(how="all")
df.columns = [str(c).strip() for c in df.columns]
st.subheader("Vista previa")
st.dataframe(df.head(), use_container_width=True)

# 3) elegir columna de fecha
date_candidates = [c for c in df.columns if any(k in str(c).lower() for k in ["fecha", "date", "periodo", "período", "mes", "month", "dia", "día"])]
date_col = st.selectbox("Columna de fecha", date_candidates if date_candidates else df.columns)

# normalizar fecha
df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
df = df.dropna(subset=[date_col]).sort_values(date_col)

# 4) detectar/convertir numéricas
num_cols = df.select_dtypes(include="number").columns.tolist()
if not num_cols:
    # intentar convertir textos tipo '1.234,56'
    possible = []
    for c in df.columns:
        s = df[c].astype(str).str.replace("\u00a0", "", regex=False)
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        s_num = pd.to_numeric(s, errors="coerce")
        if s_num.notna().mean() > 0.5:
            df[c] = s_num
            possible.append(c)
    num_cols = possible

if not num_cols:
    st.error("No encontré columnas numéricas para graficar. Probá otra fila de encabezados.")
    st.stop()

ycol = st.selectbox("Variable numérica a graficar", num_cols)

# 5) filtro de fechas
dmin, dmax = df[date_col].min().date(), df[date_col].max().date()
ini, fin = st.date_input("Rango de fechas", (dmin, dmax), min_value=dmin, max_value=dmax)
mask = (df[date_col] >= pd.to_datetime(ini)) & (df[date_col] <= pd.to_datetime(fin))
dff = df.loc[mask]

# 6) gráfico
st.subheader(f"Serie: {ycol}")
fig = px.line(dff, x=date_col, y=ycol, labels={date_col: "Fecha", ycol: ycol})
st.plotly_chart(fig, use_container_width=True)

# métrica + tabla
if not dff.empty:
    last = dff.iloc[-1]
    st.metric("Último valor", f"{last[ycol]:,.0f}", help=f"Fecha: {last[date_col].date()}")
with st.expander("Ver datos"):
    st.dataframe(dff[[date_col, ycol]], use_container_width=True)
