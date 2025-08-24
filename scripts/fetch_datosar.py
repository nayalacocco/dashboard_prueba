# scripts/fetch_datosar.py
from datosar_utils import fetch_to_long_from_allowlist, DATA

def main():
    print("[DatosAR] Descargando series de allowlist…")
    cat, long = fetch_to_long_from_allowlist()
    print(f"[DatosAR] OK. Catálogo: {len(cat):,} filas. Long: {len(long):,} filas.")
    print(f" -> {DATA / 'datosar_long.parquet'}")

if __name__ == "__main__":
    main()
