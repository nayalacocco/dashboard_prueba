import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Visualizador Económico", layout="wide")
st.title("Visualizador de Excel Monetario 📊")

file = st.file_uploader("Subí tu Excel (.xlsx)", type=["xlsx"])

# ---------- utilidades ----------
def detect_date_col(df: pd.DataFrame) -> str | None:
    # 1) candidatos por nombre
    keys = ["fecha", "date", "período", "periodo", "mes", "month", "día", "dia"]
    cand = [c for c in df.columns if any(k in str(c).lower() for k in keys)]

    def parse_ratio(series) -> float:
        s = pd.to_datetime(series, errors="coerce", dayfirst=True)
        return float(s.notna().mean())

    # 2) quedarme con los que realmente parsean a fecha
    cand = [c for c in cand if parse_ratio(df[c]) > 0.5]

    if cand:
        # el mejor por ratio
        cand.sort(key=lambda c: parse_ratio(df[c]), reverse=True)
        return cand[0]

    # 3) no hubo por nombre: probar TODAS y elegir la más “fecha”
    scores = {c: parse_ratio(df[c]) for c in df.columns}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def coerce_numeric_cols(df: pd.DataFrame) -> list[str]:
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        return num_cols

    # intentar convertir texto con miles y coma decimal
    converted = []
    for c in df.columns:
        s = df[c].astype(str).str.replace("\u00a0", "", regex=False)  # NBSP
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        s = pd.to_numeric(s, errors="coerce")
        if s.notna().mean() > 0.5:
            df[c] = s
            converted.append(c)
    return converted

# ---------- app ----------
if file:
    try:
        # Cargar HOJA correcta (siempre tiene ese nombre en tu archivo)
        raw = pd.read_excel(file, sheet_name="DATOS | DATA", header=None)

        # Hallar fila de encabezados buscando dónde aparece “Date/Fecha”
        header_row = None
        for i in range(min(60, len(raw))):  # escaneo primeras 60 filas
            row = raw.iloc[i].astype(str).str.lower()
            if row.str.contains("date").any() or row.str_contains("fecha", regex=False).any():
                header_row = i
                break
        if header_row is None:
            st.error("No encontré una fila de encabezados (no aparece 'Date'/'Fecha').")
            st.write("Vista preliminar:", raw.head(15))
            st.stop()

        df = pd.read_excel(file, sheet_name="DATOS | DATA", header=header_row)
        # tirar columnas totalmente vacías y filas vacías
        df = df.dropna(axis=1, how="all").dropna(how="all")
        df.columns = df.columns.map(lambda x: str(x).strip())

        # detectar columna fecha
        fecha_col = detect_date_col(df)
        if not fecha_col:
            st.error("No pude detectar una columna de fecha en el Excel.")
            st.write("Columnas:", list(df.columns))
            st.stop()

        # normalizar fecha
        df[fecha_col] = pd.to_datetime(df[fecha_col], errors="coerce", dayfirst=True)
        df = df.dropna(subset=[fecha_col]).sort_values(fecha_col)

        # detectar/convertir numéricas
        numeric_cols = coerce_numeric_cols(df)
        if not numeric_cols:
            st.error("No encontré columnas numéricas para graficar.")
            st.write("Columnas:", list(df.columns))
            st.stop()

        st.sidebar.header("Parámetros")
        ycol = st.sidebar.selectbox("Variable a graficar", numeric_cols)

        # filtro de fechas (por defecto: todo)
        dmin, dmax = df[fecha_col].min().date(), df[fecha_col].max().date()
        f_ini, f_fin = st.sidebar.date_input("Rango de fechas", (dmin, dmax), min_value=dmin, max_value=dmax)
        mask = (df[fecha_col] >= pd.to_datetime(f_ini)) & (df[fecha_col] <= pd.to_datetime(f_fin))
        dff = df.loc[mask]

        st.subheader(f"Serie: {ycol}")
        fig = px.line(dff, x=fecha_col, y=ycol, labels={fecha_col: "Fecha", ycol: ycol})
        st.plotly_chart(fig, use_container_width=True)

        # métrica último dato
        if not dff.empty:
            last = dff.iloc[-1]
            st.metric("Último valor", f"{last[ycol]:,.0f}", help=f"Fecha: {last[fecha_col].date()}")

        with st.expander("Ver tabla"):
            st.dataframe(dff, use_container_width=True)

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
else:
    st.info("Subí tu archivo Excel (.xlsx) con la hoja **'DATOS | DATA'**.")
