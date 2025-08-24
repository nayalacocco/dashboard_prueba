# scripts/fetch_datosar.py
from datosar_utils import (
    fetch_all_and_save,
    build_catalog_from_raw,
    build_allowlist,
    CATALOG_META_OUT,
    ALLOWLIST_OUT,
)

def main():
    print("[DatosAR] Leyendo catálogo local…")
    cat = build_catalog_from_raw()  # usa data/raw/*
    with open(ALLOWLIST_OUT, "r", encoding="utf-8") as f:
        ids = [ln.strip() for ln in f if ln.strip()]
    print(f"[DatosAR] Bajando {len(ids):,} series…")
    long_df = fetch_all_and_save(ids, catalog=cat)
    print(f"[DatosAR] Hecho. Rows: {len(long_df):,}")

if __name__ == "__main__":
    main()
