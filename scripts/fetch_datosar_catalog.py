# scripts/fetch_datosar_catalog.py
import pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW  = DATA / "raw"
RAW.mkdir(parents=True, exist_ok=True)

SRC = RAW / "series-tiempo-metadatos.csv"  # <<-- leemos el CSV local
SMALL_CSV = DATA / "datosar_metacatalog.csv"
PARQUET   = DATA / "datosar_catalog_meta.parquet"

def pick_first(*candidates, cols):
    low = {c.lower(): c for c in cols}
    for name in candidates:
        if name.lower() in low:
            return low[name.lower()]
    return None

def main():
    if not SRC.exists():
        raise SystemExit(f"No encuentro el archivo: {SRC}")

    df = pd.read_csv(SRC)

    cols = list(df.columns)
    col_id    = pick_first("id", "serie_id", cols=cols)
    col_title = pick_first("titulo", "title", "nombre", cols=cols)
    col_org   = pick_first("organismo", "publisher", "entidad", cols=cols)
    col_units = pick_first("units", "unidad_medida", cols=cols)
    col_theme = pick_first("theme", "tema", cols=cols)
    col_freq  = pick_first("periodicidad", "frecuencia", "periodicity", cols=cols)

    keep = [c for c in [col_id, col_title, col_org, col_units, col_theme, col_freq] if c]
    if not keep:
        raise RuntimeError("No pude mapear columnas básicas en el metadato.")

    small = df[keep].copy()
    rename = {}
    if col_id:    rename[col_id]    = "id"
    if col_title: rename[col_title] = "name"
    if col_org:   rename[col_org]   = "org"
    if col_units: rename[col_units] = "units"
    if col_theme: rename[col_theme] = "theme"
    if col_freq:  rename[col_freq]  = "freq"
    small.rename(columns=rename, inplace=True)

    for c in ["name","org","theme","units","freq"]:
        if c in small.columns:
            small[c] = small[c].astype(str).str.strip()

    small.to_csv(SMALL_CSV, index=False)
    small.to_parquet(PARQUET, index=False)
    print(f"[DatosAR] OK → {SMALL_CSV} / {PARQUET}")

if __name__ == "__main__":
    main()
