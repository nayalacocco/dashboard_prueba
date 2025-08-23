# scripts/fetch_datosar.py
from __future__ import annotations

import sys
from pathlib import Path
import importlib.util

# --- Cargar datosar_utils por ruta absoluta (bulletproof) ---
ROOT = Path(__file__).resolve().parents[1]
UTIL = ROOT / "datosar_utils.py"
if not UTIL.exists():
    raise FileNotFoundError(f"No encuentro {UTIL}")

spec = importlib.util.spec_from_file_location("datosar_utils", str(UTIL))
datosar_utils = importlib.util.module_from_spec(spec)
sys.modules["datosar_utils"] = datosar_utils
assert spec.loader is not None
spec.loader.exec_module(datosar_utils)  # type: ignore

# Ahora los imports funcionan como siempre
from datosar_utils import fetch_datosar_to_disk, load_datosar_long  # noqa: E402

def main():
    metas, wide = fetch_datosar_to_disk()
    # Log breve para el workflow
    print(f"[datosar] series guardadas: {len(metas)} | columnas wide: {len(wide.columns)}")

if __name__ == "__main__":
    main()
