# scripts/fetch_datosar_catalog.py
from pathlib import Path
from datosar_utils import (
    RAW, DATA,
    build_catalog_and_allowlist_from_csv,
)

# Ruta del CSV local de metadatos (el pesado que subiste)
CSV = RAW / "series-tiempo-metadatos.csv"

# Keywords iniciales (se puede ampliar cuando quieras)
KEYWORDS = [
    # Fiscal / Tesoro
    "resultado primario", "resultado financiero",
    "gasto total", "gasto primario", "ingreso", "recaudación", "recaudacion",
    "déficit", "deficit", "superávit", "superavit",
    # Inflación / IPC / INDEC
    "ipc", "precios al consumidor", "inflación", "inflacion", "nivel general",
    # Actividad / otras
    "pbi", "actividad industrial", "desempleo", "exportaciones", "importaciones",
]

def main():
    print("[DatosAR] Construyendo catálogo desde CSV local…")
    cat = build_catalog_and_allowlist_from_csv(CSV, KEYWORDS)
    print(f"[DatosAR] Catálogo reducido: {len(cat):,} series")
    print(f" -> {DATA / 'datosar_catalog_meta.parquet'}")
    print(f" -> {DATA / 'datosar_allowlist.txt'}")

if __name__ == "__main__":
    main()
