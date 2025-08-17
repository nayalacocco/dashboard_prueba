# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Visualizador Económico BCRA", layout="wide")
st.title("Visualizador de Excel Monetario 📊")

# ---------- utilidades ----------
def encontrar_fila_header(xlsx, sheet="DATOS | DATA", scan_filas=80) -> int | None:
    """Busca la primera fila que contenga 'Date' o 'Fecha' (case-insensitive)."""
    tmp = pd.read_excel(xlsx, sheet_name=sheet, header=None, nrows=scan_filas)
    for i in range(len(tmp)):
        row = tmp.iloc[i].astype(str).str.lower()
        if row.str.contains("date").any() or row.str.contains("fecha").any():
            return i
    return None

def detectar_columna_fecha(df: pd.DataFrame) -> str | None:
    """Primero intenta por nombre; si no, elige la columna que mejor parsea a fecha."""
    # candidatos por nombre
    keys = ["fecha", "date", "período", "periodo", "mes", "month", "día", "dia"]
    candidatos = [c for c in df.columns if isinstance(c, str) and any(k in c.lower() for k in keys)]

    def ratio_fecha(s: pd.Series) -> float:
        try:
            parsed = pd.to_datetime(s, errors="coerce", dayfirst=True)
            return float(parsed.notna().mean())
        except Exception:
            return 0.0

    candidatos = sorted(candidatos, key=lambda c: ratio_fecha(df[c]), reverse=True)
    if candidatos and ratio_fecha(df[candidatos[0]]) > 0:
        return candidatos[0]

    # probar todas
    ratios = {c: ratio_fecha(df[c]) for c in df.columns}
    best = max(ratios, key=ratios.get)
    return best if ratios[best] > 0 else None

def convertir_numericas(df: pd.DataFrame) -> list[str]:
    """Devuelve lista de columnas numéricas; intenta convertir texto con separadores."""
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        return num_cols

    convertidas = []
    for c in df.columns:
        s = df[c].astype(str).str.replace("\u00a0", "", regex=False)  # NBSP
        # quitar miles '.', cambiar coma decimal por '.'
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

# 1) detectar fila de encabezados
fila_header = encontrar_fila_header(archivo, sheet="DATOS | DATA")
if fila_header is None:
    st.error("No pude encontrar una fila de encabezados con 'Date' o 'Fecha' en la hoja 'DATOS | DATA'.")
    st.stop()

# 2) leer datos usando esa fila como header
df = pd.read_excel(archivo, sheet_name="DATOS | DATA", header=fila_header)
# tirar columnas/filas completamente vacías
df = df.dropna(axis=1, how="all").dropna(how="all")
# normalizar nombres
df.columns = [str(c).strip() for c in df.columns]

st.subheader("Vista previa")
st.dataframe(df.head(), use_container_width=True)

# 3) detectar y normalizar columna de fecha
fecha_col = detectar_columna_fecha(df)
if not fecha_col:
    st.error("No pude detectar una columna de fecha. Columnas leídas: " + ", ".join(map(str, df.columns)))
    st.stop()

df[fecha_col] = pd.to_datetime(df[fecha_col], errors="coerce", dayfirst=True)
df = df.dropna(subset=[fecha_col]).sort_values(fecha_col)

# 4) detectar/convertir numéricas
numeric_cols = convertir_numericas(df)
if not numeric_cols:
    st.error("No encontré columnas numéricas para graficar luego de convertir formatos.")
    st.write("Columnas detectadas:", list(df.columns))
    st.stop()

# 5) UI: selección de variable y filtro de fechas
st.sidebar.header("Parámetros")
ycol = st.sidebar.selectbox("Variable a graficar", numeric_cols, index=0)

dmin, dmax = df[fecha_col].min().date(), df[fecha_col].max().date()
rango = st.sidebar.date_input("Rango de fechas", (dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(rango, tuple) and len(rango) == 2:
    f_ini, f_fin = pd.to_datetime(rango[0]), pd.to_datetime(rango[1])
else:
    f_ini, f_fin = pd.to_datetime(dmin), pd.to_datetime(dmax)

mask = (df[fecha_col] >= f_ini) & (df[fecha_col] <= f_fin)
dff = df.loc[mask]

# 6) gráfico
st.subheader(f"Serie: {ycol}")
fig = px.line(dff, x=fecha_col, y=ycol, labels={fecha_col: "Fecha", ycol: ycol})
st.plotly_chart(fig, use_container_width=True)

# 7) métrica último dato + tabla opcional
if not dff.empty:
    last = dff.iloc[-1]
    st.metric("Último valor", f"{last[ycol]:,.0f}", help=f"Fecha: {last[fecha_col].date()}")

with st.expander("Ver datos"):
    st.dataframe(dff[[fecha_col, ycol]], use_container_width=True)
