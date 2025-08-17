import pandas as pd

# Cargar el archivo Excel
archivo = 'infomondia.xlsx'
df_raw = pd.read_excel(archivo, sheet_name='DATOS | DATA', header=None)

# Buscar la fila donde está el encabezado que contiene "Base monetaria total"
fila_header = None
for i, row in df_raw.iterrows():
    if row.astype(str).str.contains("Base monetaria total", case=False).any():
        fila_header = i
        break

if fila_header is None:
    raise ValueError("No se encontró el encabezado de 'Base monetaria total'.")

# Usar esa fila como encabezado
df = pd.read_excel(archivo, sheet_name='DATOS | DATA', header=fila_header)

# Eliminar columnas que están completamente vacías
df = df.dropna(axis=1, how='all')

# Renombrar la columna de fecha si hace falta
fecha_col = [col for col in df.columns if "date" in str(col).lower()][0]
df.rename(columns={fecha_col: "Fecha"}, inplace=True)

# Eliminar filas sin fecha
df = df[df["Fecha"].notna()]

# Asegurar que la columna de fecha esté en formato datetime
df["Fecha"] = pd.to_datetime(df["Fecha"], errors='coerce')

# Eliminar filas con fechas no válidas
df = df[df["Fecha"].notna()]

# Extraer columna de interés
columna_bm = [col for col in df.columns if "Base monetaria total" in str(col)][0]
df_bm = df[["Fecha", columna_bm]].copy()
df_bm.rename(columns={columna_bm: "Base Monetaria Total"}, inplace=True)

# Opcional: convertir a numérico y eliminar NaNs
df_bm["Base Monetaria Total"] = pd.to_numeric(df_bm["Base Monetaria Total"], errors='coerce')
df_bm.dropna(inplace=True)

# Mostrar o retornar
print(df_bm.head())
