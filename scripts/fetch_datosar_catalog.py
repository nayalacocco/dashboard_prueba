# scripts/fetch_datosar_catalog.py
import pandas as pd
from pathlib import Path

CAT_PATH = Path("data/datosar_catalog.csv")
OUT_META = Path("data/datosar_catalog_meta.parquet")

def main():
    if not CAT_PATH.exists():
        raise FileNotFoundError(f"No existe {CAT_PATH}. Crealo primero.")

    df = pd.read_csv(CAT_PATH, dtype=str).fillna("")
    required = ["group", "name", "source", "id_or_url", "units"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Faltan columnas en catalog: {missing}")

    # normalizaciones menores
    df["source"] = df["source"].str.strip().str.lower()
    df["id_or_url"] = df["id_or_url"].str.strip()

    # guardo una copia en parquet para consumo rápido
    OUT_META.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_META, index=False)
    print(f"[DatosAR] Catálogo validado: {len(df)} filas -> {OUT_META}")

if __name__ == "__main__":
    main()
