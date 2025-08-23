# scripts/fetch_mecon.py
from __future__ import annotations
import sys
from pathlib import Path

# importa de tu módulo de utilidades (mecon_utils.py)
from mecon_utils import fetch_mecon_to_disk, load_mecon_long


def main() -> int:
    print("▶ Fetch MECON → data/mecon_long.parquet")

    # baja y guarda parquet + catálogo
    df = fetch_mecon_to_disk()

    out = Path("data/mecon_long.parquet")
    if out.exists():
        print(f"✔ Guardado: {out} ({out.stat().st_size/1024:.1f} KiB)")

    print(f"Filas totales: {len(df):,}")

    # verificación rápida
    try:
        df2 = load_mecon_long()
        assert len(df2) == len(df)
    except Exception as e:
        print("WARN: verificación de lectura falló:", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
