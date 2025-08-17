# streamlit_app.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Visualizador BCRA", layout="wide")
st.title("Visualizador de Excel Monetario 📊")

# ---------- utilidades ----------
def encontrar_fila_header(xlsx, hoja="DATOS | DATA", max_scan=100):
    tmp = pd.read_excel(xlsx, sheet_name=hoja, header=None, nrows=max_scan)
    for i in range(len(tmp)):
        row = tmp.iloc[i].astype(str).str.lower()
        if row.str.contains("date").any() or row.str.contains("fecha").any():
            return i
    return None

def detectar_columna_fecha(df: pd.DataFrame):
    keys = ["fecha", "date", "periodo", "período", "mes", "month", "dia", "día"]
    candidatos = [c for c in df.columns if isinstance(c, str) and any(k in c.lower() for k in keys)]
    def score(s: pd.Series):
        return pd.to_datetime(s, errors="coerce", dayfirst=True).notna().mean()
    candidatos = sorted(candidatos, key=lambda c: score(df[c]), reverse=True)
    if candidatos and score(df[candidatos[0]]) > 0:
        return candidatos[0]
    # probar todas
    ratios = {c: score(df[c]) for c in df.columns}
    mejor = max(ratios, key=ratios.get)
    return mejor if ratios[mejor] > 0 else None

def convertir_a_numeros(df: pd.DataFrame):
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        return num_cols
    convertidas = []
    for c in df.columns:
        s = df[c].astype(str).str.replace("\u00a0", "", regex=False)
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        s_num = pd.to_numeric(s, errors="coerce")
        if s_num.notna().mean() > 0.5:
            df[c] = s_num
            convertidas.append(c)
    return convertidas

# ---------- app ----------
archivo = st.file_uploader("Subí tu Excel (.xlsx) con la hoja **'DATOS | DATA'**", type=["xlsx"])
if not archivo:
    st.info("Esperando archivo…")
    st.stop()

fila_header = encontrar_fila_header(archivo, "DATOS | DATA")
if fila_header is None:
    st.error("No encontré una fila de encabezados con 'Date' o 'Fecha' en la hoja 'DATOS | DATA'.")
    st.stop()

df = pd.read_excel(archivo, sheet_name="DATOS | DATA", header=fila_header)
df = df.dropna(axis=1, how="all").dropna(how="all")
df.columns = [str(c).strip() for c in df.columns]

fecha_col = detectar_columna_fecha(df)
if not fecha_col:
    st.error("No pude detectar una columna de fecha. Columnas leídas: " + ", ".join(map(str, df.columns)))
    st.stop()

df[fecha_col] = pd.to_datetime(df[fecha_col], errors="coerce", dayfirst=True)
df = df.dropna(subset=[fecha_col]).sort_values(fecha_col)

numeric_cols = convertir_a_numeros(df)
if not numeric_cols:
    st.error("No encontré columnas numéricas para graficar luego de convertir formatos.")
    st.write("Columnas detectadas:", list(df.columns))
    st.stop()

st.sidebar.header("Parámetros")
ycol = st.sidebar.selectbox("Variable a graficar", numeric_cols)

dmin, dmax = df[fecha_col].min().date(), df[fecha_col].max().date()
ini, fin = st.sidebar.date_input("Rango de fechas", (dmin, dmax), min_value=dmin, max_value=dmax)
mask = (df[fecha_col] >= pd.to_datetime(ini)) & (df[fecha_col] <= pd.to_datetime(fin))
dff = df.loc[mask]

st.subheader(f"Serie: {ycol}")
st.line_chart(dff.set_index(fecha_col)[ycol])
if not dff.empty:
    last = dff.iloc[-1]
    st.metric("Último valor", f"{last[ycol]:,.0f}", help=f"Fecha: {last[fecha_col].date()}")

with st.expander("Ver datos"):
    st.dataframe(dff[[fecha_col, ycol]], use_container_width=True)
