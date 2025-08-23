# scripts/fetch_datosar.py
from pathlib import Path
import sys

# asegurar import desde raíz del repo
sys.path.append(str(Path(__file__).resolve().parents[1]))

from datosar_utils import fetch_datosar_to_disk, DATA_DIR, ALLOWLIST

if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Podés precargar IDs en data/datosar_allowlist.txt (uno por línea).
    # Si está vacío, usa keywords por defecto (resultado primario, ingreso, gasto, etc.)
    metas, wide = fetch_datosar_to_disk()
    print(f"OK catálogo: {len(metas)} series")
    print(f"OK valores   shape={wide.shape}")
    if not ALLOWLIST.exists():
        ALLOWLIST.write_text(
            "# Opcional: poné acá IDs de series que querés forzar a bajar.\n# Un ID por línea.\n",
            encoding="utf-8"
        )
