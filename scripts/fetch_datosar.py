# scripts/fetch_datosar.py
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
import pandas as pd
from datosar_utils import fetch_ids_to_long, save_long

CATALOG_META_OUT = "data/datosar_catalog_meta.parquet"  # lo genera el script de catálogo
ALLOWLIST_OUT    = "data/datosar_allowlist.txt"         # lo genera el script de catálogo
LONG_OUT         = "data/datosar_long.parquet"

def main():
    print("[DatosAR] Leyendo catálogo local + allowlist…")
    cat = pd.read_parquet(CATALOG_META_OUT)  # columnas: id, name, source
    id_to_name = dict(zip(cat["id"], cat["name"]))

    ids = [ln.strip() for ln in Path(ALLOWLIST_OUT).read_text(encoding="utf-8").splitlines() if ln.strip()]
    print(f"[DatosAR] Bajando {len(ids):,} series…")

    long_df = fetch_ids_to_long(ids)  # columnas: descripcion (id), fecha, valor

    # mapear ID -> nombre “humano” para que la UI muestre nombres amigables
    long_df["descripcion"] = long_df["descripcion"].map(id_to_name).fillna(long_df["descripcion"])

    save_long(long_df, LONG_OUT)
    print(f"[DatosAR] Hecho. Rows: {len(long_df):,}")
    print(f"         -> {LONG_OUT}")

if __name__ == "__main__":
    main()
