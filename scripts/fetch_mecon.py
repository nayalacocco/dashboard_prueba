# scripts/fetch_mecon.py
from __future__ import annotations
import sys
from pathlib import Path

# Asegura que el root del repo esté en el PYTHONPATH
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from mecon_utils import fetch_mecon_to_disk, load_mecon_long  # noqa

if __name__ == "__main__":
    df = fetch_mecon_to_disk()  # baja y guarda en data/mecon_long.parquet
    print(f"OK MECON: {len(df):,} filas guardadas en data/mecon_long.parquet")
